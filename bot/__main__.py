"""Entrypoint for `python -m bot`.

Usage:
    BOT_TOKEN=123:abc python -m bot

Or, if you set BOT_TOKEN in bot/.env:
    python -m bot
"""

from __future__ import annotations

import logging

from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import Config, configure_logging
from bot.freepik_client import FreepikClient
from bot.handlers import admin as admin_mod
from bot.handlers import buy as buy_mod
from bot.handlers import generate as generate_mod
from bot.handlers import history as history_mod
from bot.handlers import keys as keys_mod
from bot.handlers import start as start_mod
from bot.storage import Storage

logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    cfg: Config = app.bot_data["config"]
    storage = Storage(cfg.db_path)
    await storage.init()
    app.bot_data["storage"] = storage
    app.bot_data["freepik_client"] = FreepikClient(base=cfg.freepik_base)

    # Bootstrap admins from env so a fresh DB is usable immediately.
    for admin_id in cfg.admin_user_ids:
        try:
            await storage.add_admin(admin_id, note="bootstrap from ADMIN_USER_IDS")
        except Exception as exc:
            logger.warning("could not bootstrap admin %s: %s", admin_id, exc)

    logger.info("storage ready at %s", cfg.db_path)
    logger.info(
        "operator keys from env: %d, admins from env: %d, allow_byo_keys=%s",
        len(cfg.operator_freepik_keys),
        len(cfg.admin_user_ids),
        cfg.allow_byo_keys,
    )


async def _post_shutdown(app: Application) -> None:
    client = app.bot_data.get("freepik_client")
    if client is not None:
        await client.aclose()


def main() -> None:
    config = Config.from_env()
    configure_logging(config.log_level)

    app = (
        ApplicationBuilder()
        .token(config.bot_token)
        .rate_limiter(AIORateLimiter())
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["config"] = config

    # Standalone commands
    app.add_handler(CommandHandler("start", start_mod.cmd_start))
    app.add_handler(CommandHandler("help", start_mod.cmd_help))
    app.add_handler(CommandHandler("menu", start_mod.cmd_menu))

    # BYO key commands (respond with /buy hint when ALLOW_BYO_KEYS=0)
    app.add_handler(CommandHandler("addkey", keys_mod.cmd_addkey))
    app.add_handler(CommandHandler("listkeys", keys_mod.cmd_listkeys))
    app.add_handler(CommandHandler("delkey", keys_mod.cmd_delkey))
    app.add_handler(CommandHandler("clearkeys", keys_mod.cmd_clearkeys))

    # Subscription / billing
    for handler in buy_mod.buy_handlers():
        app.add_handler(handler)
    # /paid via photo caption
    app.add_handler(
        MessageHandler(filters.PHOTO & filters.CaptionRegex(r"^/paid"), buy_mod.cmd_paid)
    )

    # History + stop
    app.add_handler(CommandHandler("history", history_mod.cmd_history))
    app.add_handler(CommandHandler("stop", generate_mod.cmd_stop))

    # Admin commands + inline approve/reject
    for handler in admin_mod.admin_handlers():
        app.add_handler(handler)
    app.add_handler(
        CallbackQueryHandler(admin_mod.on_admin_callback, pattern=r"^adm:")
    )

    # Plan picker callback
    app.add_handler(
        CallbackQueryHandler(buy_mod.on_plan_pick, pattern=r"^buy:")
    )
    # Menu shortcut callback (Plans / Me)
    app.add_handler(
        CallbackQueryHandler(start_mod.on_goto_callback, pattern=r"^goto:")
    )

    # Conversation flow (mode picker → model picker → prompt → media → run)
    app.add_handler(generate_mod.build_conversation_handler())

    logger.info("bot starting (long-poll)…")
    app.run_polling(allowed_updates=None, drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("shutting down")
    except Exception:  # pylint: disable=broad-except
        logger.exception("fatal error")
        raise
