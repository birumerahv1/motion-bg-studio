"""Admin-only commands: payments review, operator-key management, settings."""

from __future__ import annotations

import asyncio
import logging
import time

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from ..billing import (
    PLANS,
    format_idr,
    get_plan,
    humanize_seconds_until,
    now_ts,
)
from ..freepik_client import fingerprint_key
from ..storage import Payment
from ._common import (
    get_config,
    get_storage,
    is_admin,
)

log = logging.getLogger(__name__)


# -------------------- guards --------------------


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    msg = update.effective_message
    if user is None or msg is None:
        return False
    if not await is_admin(context, user.id):
        await msg.reply_text("Hanya admin yang bisa pakai command ini.")
        return False
    return True


# -------------------- /admin (dashboard) --------------------


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    storage = get_storage(context)
    cfg = get_config(context)
    pending = await storage.list_payments(status="pending", limit=200)
    op_keys = await storage.list_operator_keys(include_disabled=True)
    op_active = sum(1 for k in op_keys if not k.disabled)
    op_total = len(op_keys) + len(cfg.operator_freepik_keys)
    admins = await storage.list_admins()
    user_count = len(await storage.list_user_ids())
    text = (
        "🛠 *Admin Dashboard*\n"
        f"• Pending payments: *{len(pending)}*\n"
        f"• Operator Freepik keys aktif: *{op_active + len(cfg.operator_freepik_keys)}* "
        f"(total {op_total})\n"
        f"• Admins: *{len(admins) + len(cfg.admin_user_ids)}*\n"
        f"• Users tercatat: *{user_count}*\n\n"
        "Commands:\n"
        "`/payments` — list payment pending\n"
        "`/approve <id>` `/reject <id> [alasan]`\n"
        "`/opaddkey FPSX… [label]` `/oplistkeys` `/opdelkey <id>`\n"
        "`/setqris` (reply ke foto QRIS) `/setbank <text>` `/setsupport @user`\n"
        "`/setadmin <user_id> [note]` `/unsetadmin <user_id>` `/listadmins`\n"
        "`/setplan <user_id> <plan_id> [days]`\n"
        "`/broadcast <pesan>`\n"
        "`/stats`\n"
    )
    await msg.reply_text(text, parse_mode="Markdown")


# -------------------- /payments --------------------


async def cmd_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    storage = get_storage(context)
    args = (context.args or []) if context.args is not None else []  # type: ignore[attr-defined]
    status = args[0] if args else "pending"
    if status not in ("pending", "approved", "rejected", "all"):
        await msg.reply_text("Status: pending | approved | rejected | all")
        return
    rows = await storage.list_payments(
        status=None if status == "all" else status, limit=20
    )
    if not rows:
        await msg.reply_text(f"Tidak ada payment dengan status `{status}`.", parse_mode="Markdown")
        return
    out = [f"*Payments ({status})* — {len(rows)} terbaru:"]
    for p in rows:
        plan = get_plan(p.plan_id)
        plan_name = plan.name if plan else p.plan_id
        label = await storage.get_user_label(p.user_id)
        out.append(
            f"#{p.id} • {p.status} • {plan_name} • {format_idr(p.amount_idr)}"
            f"\n   user: {label} (id:`{p.user_id}`)  ref: `{p.reference_code}`"
        )
    await msg.reply_text("\n".join(out), parse_mode="Markdown")


# -------------------- /approve, /reject --------------------


def _parse_payment_id(args: list[str]) -> int | None:
    if not args:
        return None
    try:
        return int(args[0])
    except ValueError:
        return None


async def _activate_subscription(
    context: ContextTypes.DEFAULT_TYPE,
    payment: Payment,
) -> tuple[bool, str]:
    storage = get_storage(context)
    plan = get_plan(payment.plan_id)
    if plan is None:
        return False, f"Plan `{payment.plan_id}` tidak dikenal."
    now = now_ts()
    sub = await storage.get_subscription(payment.user_id)
    # Extend if same plan & still active, else replace.
    if sub and sub.plan_id == plan.id and sub.expires_at > now:
        new_expires = sub.expires_at + plan.period_seconds
        new_used = sub.quota_used  # do not reset on extension
    else:
        new_expires = now + plan.period_seconds
        new_used = 0
    await storage.upsert_subscription(
        user_id=payment.user_id,
        plan_id=plan.id,
        started_at=now,
        expires_at=new_expires,
        quota_used=new_used,
    )
    return True, (
        f"Plan *{plan.name}* aktif sampai "
        f"`{time.strftime('%Y-%m-%d %H:%M', time.localtime(new_expires))}` "
        f"({humanize_seconds_until(new_expires, now=now)})."
    )


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    user = update.effective_user
    args = list(context.args or [])  # type: ignore[attr-defined]
    pid = _parse_payment_id(args)
    if pid is None:
        await msg.reply_text("Pakai: `/approve <payment_id>`", parse_mode="Markdown")
        return
    storage = get_storage(context)
    payment = await storage.get_payment(pid)
    if payment is None:
        await msg.reply_text(f"Payment #{pid} tidak ditemukan.")
        return
    if payment.status != "pending":
        await msg.reply_text(f"Payment #{pid} status: {payment.status}, tidak bisa di-approve.")
        return
    ok, info = await _activate_subscription(context, payment)
    if not ok:
        await msg.reply_text(info, parse_mode="Markdown")
        return
    await storage.set_payment_status(
        pid, "approved", reviewed_by=user.id if user else None
    )
    await msg.reply_text(f"Payment #{pid} approved. {info}", parse_mode="Markdown")
    # Notify the user.
    try:
        await context.bot.send_message(
            chat_id=payment.user_id,
            text=(
                f"✅ Pembayaran kamu untuk *{(get_plan(payment.plan_id) or PLANS['free']).name}* "
                f"sudah disetujui.\n{info}\nKetik /menu untuk mulai generate."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        log.warning("notify approve to %s failed: %s", payment.user_id, e)


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    user = update.effective_user
    args = list(context.args or [])  # type: ignore[attr-defined]
    pid = _parse_payment_id(args)
    if pid is None:
        await msg.reply_text("Pakai: `/reject <payment_id> [alasan]`", parse_mode="Markdown")
        return
    reason = " ".join(args[1:]).strip() or "Bukti tidak valid."
    storage = get_storage(context)
    payment = await storage.get_payment(pid)
    if payment is None:
        await msg.reply_text(f"Payment #{pid} tidak ditemukan.")
        return
    if payment.status != "pending":
        await msg.reply_text(f"Payment #{pid} status: {payment.status}, tidak bisa di-reject.")
        return
    await storage.set_payment_status(
        pid, "rejected",
        reviewed_by=user.id if user else None,
        rejection_reason=reason,
    )
    await msg.reply_text(f"Payment #{pid} rejected.")
    try:
        await context.bot.send_message(
            chat_id=payment.user_id,
            text=(
                f"❌ Pembayaran kamu (ref `{payment.reference_code}`) ditolak.\n"
                f"Alasan: {reason}\n\nKetik /buy untuk coba lagi atau hubungi admin."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        log.warning("notify reject to %s failed: %s", payment.user_id, e)


# -------------------- inline-button approve/reject --------------------


async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    user = update.effective_user
    if user is None or not await is_admin(context, user.id):
        await query.answer("Hanya admin.", show_alert=True)
        return
    parts = query.data.split(":")
    if len(parts) < 3:
        await query.answer("Bad payload.", show_alert=True)
        return
    action = parts[1]
    try:
        pid = int(parts[2])
    except ValueError:
        await query.answer("Bad payload.", show_alert=True)
        return
    storage = get_storage(context)
    payment = await storage.get_payment(pid)
    if payment is None:
        await query.answer("Tidak ditemukan", show_alert=True)
        return
    if payment.status != "pending":
        await query.answer(f"Sudah {payment.status}", show_alert=True)
        return
    if action == "approve":
        ok, info = await _activate_subscription(context, payment)
        if not ok:
            await query.answer("Plan invalid", show_alert=True)
            return
        await storage.set_payment_status(pid, "approved", reviewed_by=user.id)
        await query.answer("Approved.")
        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + f"\n\n✅ APPROVED. {info}",
                parse_mode="Markdown",
            )
        except Exception:
            await query.edit_message_text(
                text=f"Payment #{pid} approved. {info}", parse_mode="Markdown"
            )
        try:
            await context.bot.send_message(
                chat_id=payment.user_id,
                text=(
                    f"✅ Pembayaran kamu untuk *{(get_plan(payment.plan_id) or PLANS['free']).name}* "
                    f"sudah disetujui.\n{info}\nKetik /menu untuk mulai generate."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning("notify approve to %s failed: %s", payment.user_id, e)
    elif action == "reject":
        reason = "Bukti tidak valid."
        await storage.set_payment_status(
            pid, "rejected", reviewed_by=user.id, rejection_reason=reason
        )
        await query.answer("Rejected.")
        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + f"\n\n❌ REJECTED. {reason}",
                parse_mode="Markdown",
            )
        except Exception:
            await query.edit_message_text(text=f"Payment #{pid} rejected. {reason}")
        try:
            await context.bot.send_message(
                chat_id=payment.user_id,
                text=(
                    f"❌ Pembayaran kamu (ref `{payment.reference_code}`) ditolak.\n"
                    f"Alasan: {reason}\n\nKetik /buy untuk coba lagi."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning("notify reject to %s failed: %s", payment.user_id, e)
    else:
        await query.answer("Unknown action", show_alert=True)


# -------------------- operator key management --------------------


async def cmd_opaddkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/opaddkey FPSX… [label]`", parse_mode="Markdown")
        return
    api_key = args[0].strip()
    label = " ".join(args[1:]).strip() or None
    storage = get_storage(context)
    new_id = await storage.add_operator_key(api_key, label=label)
    fp = fingerprint_key(api_key)
    await msg.reply_text(f"Operator key #{new_id} ditambah ({fp}).")
    # Best-effort delete the original message so the secret is not visible.
    try:
        await msg.delete()
    except Exception:
        pass


async def cmd_oplistkeys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    storage = get_storage(context)
    cfg = get_config(context)
    db_keys = await storage.list_operator_keys(include_disabled=True)
    lines = ["*Operator Freepik keys*"]
    if cfg.operator_freepik_keys:
        for k in cfg.operator_freepik_keys:
            lines.append(f"• env • {fingerprint_key(k)}")
    if not db_keys and not cfg.operator_freepik_keys:
        lines.append("_kosong — tambah dengan /opaddkey_")
    for k in db_keys:
        flag = " (disabled)" if k.disabled else ""
        last = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(k.last_used_at))
            if k.last_used_at
            else "-"
        )
        lines.append(
            f"• #{k.id} • {fingerprint_key(k.api_key)}{flag} • last_used={last} "
            f"• label: {k.label or '-'}"
        )
    await msg.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_opdelkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/opdelkey <id>`", parse_mode="Markdown")
        return
    try:
        kid = int(args[0])
    except ValueError:
        await msg.reply_text("ID harus angka.")
        return
    ok = await get_storage(context).delete_operator_key(kid)
    await msg.reply_text("Dihapus." if ok else "Tidak ditemukan.")


async def cmd_opdisable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/opdisable <id>`", parse_mode="Markdown")
        return
    try:
        kid = int(args[0])
    except ValueError:
        await msg.reply_text("ID harus angka.")
        return
    ok = await get_storage(context).set_operator_key_disabled(kid, True)
    await msg.reply_text("Disabled." if ok else "Tidak ditemukan.")


async def cmd_openable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/openable <id>`", parse_mode="Markdown")
        return
    try:
        kid = int(args[0])
    except ValueError:
        await msg.reply_text("ID harus angka.")
        return
    ok = await get_storage(context).set_operator_key_disabled(kid, False)
    await msg.reply_text("Enabled." if ok else "Tidak ditemukan.")


# -------------------- settings (QRIS, bank, support) --------------------


async def cmd_setqris(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    target = msg.reply_to_message if msg and msg.reply_to_message else msg
    if target is None or not target.photo:
        await msg.reply_text(
            "Reply ke foto QRIS dengan command `/setqris`, atau kirim foto QRIS "
            "dengan caption `/setqris`.",
            parse_mode="Markdown",
        )
        return
    file_id = target.photo[-1].file_id
    storage = get_storage(context)
    await storage.set_setting("qris_image_file_id", file_id)
    if target.caption:
        await storage.set_setting("qris_image_caption", target.caption)
    await msg.reply_text("QRIS image disimpan.")


async def cmd_setbank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    text = (msg.text or "").split(None, 1)
    if len(text) < 2 or not text[1].strip():
        await msg.reply_text(
            "Pakai: `/setbank <multiline text>` — contoh:\n"
            "```\n/setbank BCA 1234567890 a.n. Budi Pratama\nMandiri 1110002223 a.n. Budi Pratama```",
            parse_mode="Markdown",
        )
        return
    await get_storage(context).set_setting("bank_text", text[1].strip())
    await msg.reply_text("Info rekening disimpan.")


async def cmd_setsupport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/setsupport @username`", parse_mode="Markdown")
        return
    handle = args[0].strip()
    if not handle.startswith("@"):
        handle = "@" + handle
    await get_storage(context).set_setting("support_handle", handle)
    await msg.reply_text(f"Support handle: {handle}")


# -------------------- admin management --------------------


async def cmd_setadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/setadmin <user_id> [note]`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await msg.reply_text("user_id harus angka.")
        return
    note = " ".join(args[1:]).strip() or None
    await get_storage(context).add_admin(uid, note)
    await msg.reply_text(f"User `{uid}` jadi admin.", parse_mode="Markdown")


async def cmd_unsetadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if not args:
        await msg.reply_text("Pakai: `/unsetadmin <user_id>`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await msg.reply_text("user_id harus angka.")
        return
    ok = await get_storage(context).remove_admin(uid)
    await msg.reply_text("Dihapus." if ok else "Bukan admin runtime (mungkin di env ADMIN_USER_IDS).")


async def cmd_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    cfg = get_config(context)
    storage = get_storage(context)
    runtime = await storage.list_admins()
    lines = ["*Admins*"]
    for uid in cfg.admin_user_ids:
        lines.append(f"• env • `{uid}`")
    for uid in runtime:
        if uid in cfg.admin_user_ids:
            continue
        label = await storage.get_user_label(uid)
        lines.append(f"• runtime • {label} (`{uid}`)")
    if not cfg.admin_user_ids and not runtime:
        lines.append("_kosong — tambah dengan /setadmin <user_id>_")
    await msg.reply_text("\n".join(lines), parse_mode="Markdown")


# -------------------- /setplan (manual subscription override) --------------------


async def cmd_setplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    args = list(context.args or [])  # type: ignore[attr-defined]
    if len(args) < 2:
        await msg.reply_text(
            "Pakai: `/setplan <user_id> <plan_id> [days]`\n"
            f"Plan ids: {', '.join(PLANS.keys())}",
            parse_mode="Markdown",
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await msg.reply_text("user_id harus angka.")
        return
    plan_id = args[1].strip()
    plan = get_plan(plan_id)
    if plan is None:
        await msg.reply_text(f"Plan `{plan_id}` tidak dikenal.", parse_mode="Markdown")
        return
    days_arg = args[2] if len(args) >= 3 else None
    if days_arg:
        try:
            days = int(days_arg)
        except ValueError:
            await msg.reply_text("days harus angka.")
            return
        period = days * 24 * 3600
    else:
        period = plan.period_seconds
    now = now_ts()
    await get_storage(context).upsert_subscription(
        user_id=uid,
        plan_id=plan.id,
        started_at=now,
        expires_at=now + period,
        quota_used=0,
    )
    await msg.reply_text(
        f"User `{uid}` di-set ke plan *{plan.name}* selama {period // 86400} hari.",
        parse_mode="Markdown",
    )


# -------------------- /broadcast --------------------


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    text = (msg.text or "").split(None, 1)
    if len(text) < 2 or not text[1].strip():
        await msg.reply_text(
            "Pakai: `/broadcast <pesan ke semua user>`", parse_mode="Markdown"
        )
        return
    body = text[1].strip()
    storage = get_storage(context)
    user_ids = await storage.list_user_ids()
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=body)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # gentle on Telegram limits
    await msg.reply_text(f"Broadcast: {sent} terkirim, {failed} gagal.")


# -------------------- /stats --------------------


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    msg = update.effective_message
    storage = get_storage(context)
    user_ids = await storage.list_user_ids()
    pending = await storage.list_payments(status="pending", limit=999)
    approved = await storage.list_payments(status="approved", limit=999)
    rejected = await storage.list_payments(status="rejected", limit=999)
    op_keys = await storage.list_operator_keys(include_disabled=True)
    cfg = get_config(context)
    text = (
        "📊 *Stats*\n"
        f"• Users: {len(user_ids)}\n"
        f"• Pending payments: {len(pending)}\n"
        f"• Approved payments (recent): {len(approved)}\n"
        f"• Rejected payments (recent): {len(rejected)}\n"
        f"• Operator keys total: {len(op_keys) + len(cfg.operator_freepik_keys)} "
        f"(env={len(cfg.operator_freepik_keys)}, db={len(op_keys)})\n"
    )
    await msg.reply_text(text, parse_mode="Markdown")


# -------------------- handler registration --------------------


def admin_handlers() -> list:
    return [
        CommandHandler("admin", cmd_admin),
        CommandHandler("payments", cmd_payments),
        CommandHandler("approve", cmd_approve),
        CommandHandler("reject", cmd_reject),
        CommandHandler("opaddkey", cmd_opaddkey),
        CommandHandler("oplistkeys", cmd_oplistkeys),
        CommandHandler("opdelkey", cmd_opdelkey),
        CommandHandler("opdisable", cmd_opdisable),
        CommandHandler("openable", cmd_openable),
        CommandHandler("setqris", cmd_setqris),
        CommandHandler("setbank", cmd_setbank),
        CommandHandler("setsupport", cmd_setsupport),
        CommandHandler("setadmin", cmd_setadmin),
        CommandHandler("unsetadmin", cmd_unsetadmin),
        CommandHandler("listadmins", cmd_listadmins),
        CommandHandler("setplan", cmd_setplan),
        CommandHandler("broadcast", cmd_broadcast),
        CommandHandler("stats", cmd_stats),
    ]


__all__ = ["admin_handlers", "on_admin_callback"]
