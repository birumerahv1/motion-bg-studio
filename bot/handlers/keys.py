"""API key management commands.

For privacy reasons, /addkey only accepts the key when sent in a private
1:1 chat with the bot — we do NOT want users pasting their FPSX… token
into a group chat where everyone can see it.
"""

from __future__ import annotations

import datetime as dt

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot.freepik_client import fingerprint_key
from bot.storage import Storage


def _is_private(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == ChatType.PRIVATE


async def cmd_addkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    if not _is_private(update):
        await msg.reply_text(
            "❌ Untuk keamanan, /addkey hanya berfungsi di chat pribadi 1:1 dengan saya. "
            "Buka chat private saya lalu kirim ulang perintahnya."
        )
        return

    args = context.args or []
    if not args:
        await msg.reply_markdown(
            "Format: `/addkey <FPSX-API-KEY> [label]`\n"
            "Contoh: `/addkey FPSX36395ce7a... main`\n\n"
            "API key akan disimpan **hanya** di database lokal bot. Tidak dikirim ke pihak lain."
        )
        return

    api_key = args[0].strip()
    label = " ".join(args[1:]).strip() or None

    if not api_key.startswith("FPSX"):
        await msg.reply_text(
            "Sepertinya bukan API key Freepik (harus diawali `FPSX`). "
            "Cek lagi di https://www.freepik.com/api"
        )
        return

    storage: Storage = context.application.bot_data["storage"]
    new_id = await storage.add_api_key(user.id, api_key, label)
    fp = fingerprint_key(api_key)

    # Try to delete the original message so the key doesn't sit in the chat
    # transcript longer than necessary.
    try:
        await msg.delete()
    except Exception:  # pylint: disable=broad-except
        pass

    await context.bot.send_message(
        chat_id=msg.chat_id,
        text=(
            f"✅ Key #{new_id} ditambahkan ({fp}).\n"
            f"{'Label: ' + label if label else 'Tanpa label.'}\n"
            "Pesan asli berisi key sudah saya hapus dari chat."
        ),
    )


async def cmd_listkeys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    storage: Storage = context.application.bot_data["storage"]
    keys = await storage.list_api_keys(user.id)
    if not keys:
        await msg.reply_text(
            "Belum ada API key. Tambahkan dengan /addkey <FPSX...> [label] di chat private."
        )
        return
    lines = ["🔑 *API keys Anda*"]
    for k in keys:
        added = dt.datetime.fromtimestamp(k.added_at).strftime("%Y-%m-%d")
        last = (
            dt.datetime.fromtimestamp(k.last_used_at).strftime("%Y-%m-%d %H:%M")
            if k.last_used_at
            else "—"
        )
        label = f" ({k.label})" if k.label else ""
        lines.append(
            f"#{k.id}{label} · `{fingerprint_key(k.api_key)}` · added {added} · last used {last}"
        )
    await msg.reply_markdown("\n".join(lines))


async def cmd_delkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    args = context.args or []
    if not args:
        await msg.reply_markdown("Format: `/delkey <id>` (lihat id dengan /listkeys)")
        return
    try:
        key_id = int(args[0])
    except ValueError:
        await msg.reply_text("ID harus angka.")
        return

    storage: Storage = context.application.bot_data["storage"]
    ok = await storage.delete_api_key(user.id, key_id)
    if ok:
        await msg.reply_text(f"🗑 Key #{key_id} dihapus.")
    else:
        await msg.reply_text("Key dengan id itu tidak ditemukan untuk akun Anda.")


async def cmd_clearkeys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    storage: Storage = context.application.bot_data["storage"]
    n = await storage.clear_api_keys(user.id)
    await msg.reply_text(f"🗑 {n} key dihapus.")
