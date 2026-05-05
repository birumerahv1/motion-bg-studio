"""Start, help, and the main mode-picker menu."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Config


def _welcome_text(byo_enabled: bool) -> str:
    if byo_enabled:
        key_block = (
            "Sebelum generate, tambahkan API key Freepik Anda dengan /addkey "
            "(BYO mode), atau /buy untuk pakai key operator.\n\n"
            "Perintah key:\n"
            "/listkeys — lihat key tersimpan\n"
            "/delkey <id> — hapus key berdasarkan id\n"
            "/clearkeys — hapus semua key\n"
        )
    else:
        key_block = (
            "Bot ini berjalan dengan operator key (mode SaaS). "
            "Pilih paket dengan /buy.\n\n"
        )
    return (
        "*Freepik AI Studio bot*\n\n"
        "Generate images and videos with Freepik AI langsung di Telegram.\n"
        "Mode yang tersedia:\n"
        "• 🖼 *Text → Image* (Nano Banana Pro, Seedream 4.5)\n"
        "• 🎬 *Text → Video* (Veo 3.1, Kling 3 Pro)\n"
        "• 🎞 *Image → Video* (Kling 3/2.6 Pro, Seedance Pro)\n"
        "• 💃 *Motion Control* (Kling 2.6 / Kling 3 Omni Pro)\n\n"
        + key_block
        + "\n*Subscription:*\n"
        "/plans — daftar paket & harga\n"
        "/buy — beli paket (manual QRIS / transfer)\n"
        "/me — status langganan kamu\n"
        "/paid <ref> — kirim bukti transfer untuk verifikasi admin\n\n"
        "*Lainnya:*\n"
        "/history — 10 generasi terakhir\n"
        "/menu — buka mode picker\n"
        "/cancel — batalkan flow yang lagi jalan\n"
        "/stop — batalkan generasi yang sedang berjalan"
    )


def _menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🖼 Text → Image", callback_data="mode:text-to-image"),
                InlineKeyboardButton("🎬 Text → Video", callback_data="mode:text-to-video"),
            ],
            [
                InlineKeyboardButton("🎞 Image → Video", callback_data="mode:image-to-video"),
                InlineKeyboardButton("💃 Motion Control", callback_data="mode:motion-control"),
            ],
            [
                InlineKeyboardButton("💎 Plans", callback_data="goto:plans"),
                InlineKeyboardButton("👤 Me", callback_data="goto:me"),
            ],
        ]
    )


async def _track_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    storage = context.application.bot_data.get("storage")
    if storage is None:
        return
    try:
        await storage.upsert_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
    except Exception:
        pass


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_user(update, context)
    msg = update.effective_message
    if msg is None:
        return
    cfg: Config = context.application.bot_data["config"]
    await msg.reply_markdown(
        _welcome_text(cfg.allow_byo_keys),
        reply_markup=_menu(),
        disable_web_page_preview=True,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_user(update, context)
    msg = update.effective_message
    if msg is None:
        return
    cfg: Config = context.application.bot_data["config"]
    await msg.reply_markdown(
        _welcome_text(cfg.allow_byo_keys),
        reply_markup=_menu(),
        disable_web_page_preview=True,
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_user(update, context)
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text("Pilih mode:", reply_markup=_menu())


async def on_goto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Plans / Me shortcut buttons in the main menu."""
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()
    target = query.data.split(":", 1)[1] if ":" in query.data else ""
    msg = query.message
    if msg is None:
        return
    if target == "plans":
        # Lazy import to avoid circular import at module load.
        from .buy import cmd_plans

        await cmd_plans(update, context)
    elif target == "me":
        from .buy import cmd_me

        await cmd_me(update, context)
