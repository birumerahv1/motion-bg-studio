"""User-facing purchase flow: /buy → pick plan → upload bukti → /paid."""

from __future__ import annotations

import logging
import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from ..billing import (
    PLANS,
    format_idr,
    get_plan,
    humanize_seconds_until,
    make_reference_code,
    now_ts,
    paid_plans,
)
from ._common import get_config, get_storage, is_admin

log = logging.getLogger(__name__)


def _plan_pick_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for plan in sorted(paid_plans(), key=lambda p: p.sort):
        rows.append(
            [
                InlineKeyboardButton(
                    f"{plan.name} • {format_idr(plan.price_idr)} • {plan.quota} credits",
                    callback_data=f"buy:plan:{plan.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("✖ Batal", callback_data="buy:cancel")])
    return InlineKeyboardMarkup(rows)


# -------------------- /buy --------------------


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    lines = ["💳 *Pilih paket langganan:*", ""]
    for plan in sorted(paid_plans(), key=lambda p: p.sort):
        lines.append(f"*{plan.name}* — {format_idr(plan.price_idr)} / bulan")
        lines.append(f"  • {plan.quota} credits / bulan")
        lines.append(f"  • {plan.description}")
        lines.append("")
    lines.append("_Cost rata-rata:_ image 1 credit • video pendek 3 credits • video panjang 5 credits • motion control 4 credits.")
    await msg.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=_plan_pick_keyboard()
    )


async def on_plan_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    user = update.effective_user
    if user is None:
        await query.answer()
        return
    await query.answer()
    data = query.data
    if data == "buy:cancel":
        await query.edit_message_text("Pembelian dibatalkan.")
        return
    if not data.startswith("buy:plan:"):
        return
    plan_id = data.split(":", 2)[2]
    plan = get_plan(plan_id)
    if plan is None or not plan.paid:
        await query.edit_message_text("Plan tidak dikenal.")
        return
    storage = get_storage(context)
    ref = make_reference_code(user.id)
    payment_id = await storage.insert_payment(
        user_id=user.id,
        plan_id=plan.id,
        amount_idr=plan.price_idr,
        reference_code=ref,
    )
    bank_text = await storage.get_setting("bank_text")
    qris_file_id = await storage.get_setting("qris_image_file_id")
    qris_caption = await storage.get_setting("qris_image_caption")
    support_handle = await storage.get_setting("support_handle")

    summary_parts = [
        f"📌 *Order #{payment_id}* — *{plan.name}*",
        f"💰 Jumlah: *{format_idr(plan.price_idr)}*",
        f"🔖 Kode referensi: `{ref}`",
        "",
        "*Cara bayar:*",
        "1. Transfer / scan QRIS sesuai jumlah di atas (jangan dibulatkan).",
        "2. Sertakan kode referensi `" + ref + "` pada *catatan/berita transfer* "
        "(atau sebut di caption screenshot).",
        "3. Kirim screenshot bukti transfer di chat ini, dengan caption:",
        f"   `/paid {ref}`",
        "",
    ]
    if bank_text:
        summary_parts.append("*Rekening:*\n```\n" + bank_text + "\n```")
    else:
        summary_parts.append("_Info rekening belum di-set admin. Hubungi admin dulu._")
    if support_handle:
        summary_parts.append(f"\nButuh bantuan? Hubungi {support_handle}.")
    summary_parts.append(
        "\n_Setelah admin verifikasi (biasanya < 1 jam pada jam kerja), "
        "subscription kamu otomatis aktif._"
    )
    summary = "\n".join(summary_parts)
    await query.edit_message_text(summary, parse_mode="Markdown")
    if qris_file_id:
        try:
            await context.bot.send_photo(
                chat_id=user.id,
                photo=qris_file_id,
                caption=(
                    qris_caption + "\n\n" if qris_caption else ""
                )
                + f"Scan QRIS sebesar *{format_idr(plan.price_idr)}* dan sertakan kode "
                f"referensi `{ref}` di catatan/screenshot.",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning("send qris failed: %s", e)


# -------------------- /paid --------------------


async def cmd_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User uploads a screenshot of bukti transfer with caption /paid <ref>.

    Also accepts a reply: user replies to a previous photo with /paid <ref>.
    """
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    args = list(context.args or [])  # type: ignore[attr-defined]
    storage = get_storage(context)
    payment = None
    if args:
        payment = await storage.find_pending_payment_by_ref(args[0].strip())
    if payment is None:
        # Fall back to user's latest pending payment.
        payment = await storage.find_latest_pending_payment(user.id)
    if payment is None:
        await msg.reply_text(
            "Tidak ada pembayaran pending. /buy dulu untuk pilih paket, "
            "lalu kirim bukti dengan caption `/paid <kode_ref>`.",
            parse_mode="Markdown",
        )
        return
    if payment.user_id != user.id:
        # Ref code yang dikirim user lain — tolak.
        await msg.reply_text("Kode referensi ini bukan milik kamu.")
        return

    # Find the photo in this message or the replied-to message.
    photo_msg = msg if msg.photo else (msg.reply_to_message if msg.reply_to_message else None)
    if photo_msg is None or not photo_msg.photo:
        await msg.reply_text(
            "Sertakan screenshot bukti transfer (kirim foto dengan caption "
            "`/paid <kode_ref>`, atau reply ke foto yang sudah ada).",
            parse_mode="Markdown",
        )
        return
    file_id = photo_msg.photo[-1].file_id
    caption = msg.caption or msg.text or ""
    await storage.attach_payment_proof(
        payment.id,
        file_id=file_id,
        message_id=photo_msg.message_id,
        caption=caption,
    )
    await msg.reply_text(
        f"Bukti diterima untuk order #{payment.id} (`{payment.reference_code}`). "
        "Admin akan memverifikasi sebentar lagi. Kamu akan dapat notifikasi di "
        "sini saat sudah disetujui.",
        parse_mode="Markdown",
    )

    # Notify all admins with inline approve/reject buttons.
    cfg = get_config(context)
    runtime_admins = await storage.list_admins()
    admin_ids = list({*cfg.admin_user_ids, *runtime_admins})
    plan = get_plan(payment.plan_id)
    plan_name = plan.name if plan else payment.plan_id
    user_label = await storage.get_user_label(user.id)
    notify_caption = (
        f"💸 *New payment* #{payment.id}\n"
        f"User: {user_label} (`{user.id}`)\n"
        f"Plan: *{plan_name}* ({format_idr(payment.amount_idr)})\n"
        f"Ref: `{payment.reference_code}`\n"
        f"Caption: {caption[:300] if caption else '-'}"
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:approve:{payment.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:reject:{payment.id}"),
            ]
        ]
    )
    for admin_id in admin_ids:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=notify_caption,
                parse_mode="Markdown",
                reply_markup=buttons,
            )
        except Exception as e:
            log.warning("notify admin %s failed: %s", admin_id, e)


# -------------------- /me / /sub (subscription status) --------------------


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    storage = get_storage(context)
    sub = await storage.get_subscription(user.id)
    now = now_ts()
    lines = [f"👤 *{user.first_name or 'You'}* (`{user.id}`)"]
    if sub is None:
        free = PLANS["free"]
        used = await storage.count_history_since(user.id, since_ts=now - free.period_seconds)
        remaining = max(0, free.quota - used)
        lines.append(
            f"Plan: *{free.name}* (default)\n"
            f"Quota: {used} / {free.quota} digunakan dalam 24 jam terakhir "
            f"(sisa {remaining})"
        )
        lines.append("\nKetik /buy untuk upgrade ke paket berbayar.")
    else:
        plan = get_plan(sub.plan_id) or PLANS["free"]
        if plan.paid:
            lines.append(
                f"Plan: *{plan.name}* — aktif sampai "
                f"`{time.strftime('%Y-%m-%d %H:%M', time.localtime(sub.expires_at))}` "
                f"({humanize_seconds_until(sub.expires_at, now=now)})"
            )
            lines.append(
                f"Quota: *{sub.quota_used} / {plan.quota}* credits digunakan "
                f"(sisa {max(0, plan.quota - sub.quota_used)})"
            )
            if sub.expires_at <= now:
                lines.append("\n⚠️ Subscription sudah habis. /buy untuk perpanjang.")
        else:
            used = await storage.count_history_since(
                user.id, since_ts=now - plan.period_seconds
            )
            remaining = max(0, plan.quota - used)
            lines.append(
                f"Plan: *{plan.name}*\n"
                f"Quota: {used} / {plan.quota} dalam 24 jam terakhir "
                f"(sisa {remaining})"
            )
            lines.append("\nKetik /buy untuk upgrade.")

    if await is_admin(context, user.id):
        lines.append("\n🛠 _kamu admin_ — `/admin` untuk dashboard")

    await msg.reply_text("\n".join(lines), parse_mode="Markdown")


# -------------------- /plans (price list) --------------------


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    lines = ["💎 *Daftar Paket*", ""]
    for p in sorted(PLANS.values(), key=lambda x: x.sort):
        lines.append(
            f"*{p.name}* • {format_idr(p.price_idr) if p.price_idr else 'Gratis'}"
        )
        lines.append(
            f"  • Quota: {p.quota} credits / "
            f"{'24 jam' if p.period_seconds <= 86400 else 'bulan'}"
        )
        lines.append(f"  • {p.description}")
        lines.append("")
    lines.append("Pilih dengan /buy.")
    await msg.reply_text("\n".join(lines), parse_mode="Markdown")


# -------------------- handler registration --------------------


def buy_handlers() -> list:
    return [
        CommandHandler("buy", cmd_buy),
        CommandHandler("paid", cmd_paid),
        CommandHandler("me", cmd_me),
        CommandHandler("subscription", cmd_me),
        CommandHandler("plans", cmd_plans),
    ]


__all__ = ["buy_handlers", "on_plan_pick"]
