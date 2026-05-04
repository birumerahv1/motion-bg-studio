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
    CommandHandler,
)

from bot.config import Config, configure_logging
from bot.freepik_client import FreepikClient
from bot.handlers import generate as generate_mod
from bot.handlers import history as history_mod
from bot.handlers import keys as keys_mod
from bot.handlers import start as start_mod
from bot.storage import Storage

logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    storage = Storage(app.bot_data["config"].db_path)
    await storage.init()
    app.bot_data["storage"] = storage
    app.bot_data["freepik_client"] = FreepikClient(
        base=app.bot_data["config"].freepik_base
    )
    logger.info("storage ready at %s", app.bot_data["config"].db_path)


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
    app.add_handler(CommandHandler("addkey", keys_mod.cmd_addkey))
    app.add_handler(CommandHandler("listkeys", keys_mod.cmd_listkeys))
    app.add_handler(CommandHandler("delkey", keys_mod.cmd_delkey))
    app.add_handler(CommandHandler("clearkeys", keys_mod.cmd_clearkeys))
    app.add_handler(CommandHandler("history", history_mod.cmd_history))
    app.add_handler(CommandHandler("stop", generate_mod.cmd_stop))

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
