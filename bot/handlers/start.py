"""Start, help, and the main mode-picker menu."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

WELCOME = (
    "*Freepik AI Studio bot*\n\n"
    "Generate images and videos with Freepik AI directly in Telegram.\n"
    "Mode yang tersedia:\n"
    "• 🖼 *Text → Image* (Nano Banana Pro, Seedream 4.5)\n"
    "• 🎬 *Text → Video* (Veo 3.1, Kling 3 Pro)\n"
    "• 🎞 *Image → Video* (Kling 3/2.6 Pro, Seedance Pro)\n"
    "• 💃 *Motion Control* (Kling 2.6 / Kling 3 Omni Pro)\n\n"
    "Sebelum generate, tambahkan API key Freepik Anda dengan /addkey.\n"
    "Anda bisa menambahkan beberapa key — bot akan otomatis "
    "berganti ke key berikutnya kalau ada yang expired/limit.\n\n"
    "Perintah lain:\n"
    "/listkeys — lihat key tersimpan\n"
    "/delkey <id> — hapus key berdasarkan id\n"
    "/clearkeys — hapus semua key\n"
    "/history — riwayat 10 generasi terakhir\n"
    "/cancel — batalkan flow yang lagi jalan"
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
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_markdown(WELCOME, reply_markup=_menu(), disable_web_page_preview=True)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_markdown(WELCOME, reply_markup=_menu(), disable_web_page_preview=True)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text("Pilih mode:", reply_markup=_menu())
