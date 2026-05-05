"""/history — list the user's recent generations."""

from __future__ import annotations

import datetime as dt

from telegram import Update
from telegram.ext import ContextTypes

from bot.storage import Storage

_STATUS_EMOJI = {
    "COMPLETED": "✅",
    "DONE": "✅",
    "SUCCESS": "✅",
    "SUCCEEDED": "✅",
    "FAILED": "❌",
    "ERROR": "❌",
    "CANCELED": "🚫",
    "CANCELLED": "🚫",
    "IN_PROGRESS": "⏳",
    "PENDING": "⏳",
    "QUEUED": "⏳",
    "STARTED": "⏳",
}


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    storage: Storage = context.application.bot_data["storage"]
    rows = await storage.list_history(user.id, limit=10)
    if not rows:
        await msg.reply_text(
            "Belum ada riwayat. Gunakan /menu untuk mulai generate."
        )
        return
    lines = ["📜 *10 generasi terakhir*"]
    for r in rows:
        when = dt.datetime.fromtimestamp(r.created_at).strftime("%m-%d %H:%M")
        emoji = _STATUS_EMOJI.get(r.status.upper(), "•")
        prompt_preview = (r.prompt or "")[:60].replace("\n", " ")
        suffix = ""
        if r.result_url:
            suffix = f" · [open]({r.result_url})"
        elif r.error_message:
            err = r.error_message[:60]
            suffix = f" · _{err}_"
        lines.append(
            f"{emoji} `#{r.id}` `{when}` *{r.model_id}* — {prompt_preview}{suffix}"
        )
    await msg.reply_markdown("\n".join(lines), disable_web_page_preview=True)
