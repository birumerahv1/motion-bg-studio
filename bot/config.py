"""Bot configuration from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    freepik_base: str
    poll_interval_seconds: float
    max_image_bytes: int
    max_video_bytes: int
    log_level: str

    @classmethod
    def from_env(cls) -> Config:
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Get one from @BotFather and export it as an "
                "environment variable, or put it in a .env file next to bot/."
            )
        return cls(
            bot_token=token,
            db_path=os.environ.get("DB_PATH", "bot/data/bot.db"),
            freepik_base=os.environ.get("FREEPIK_BASE", "https://api.freepik.com"),
            poll_interval_seconds=float(os.environ.get("POLL_INTERVAL", "4")),
            max_image_bytes=int(os.environ.get("MAX_IMAGE_BYTES", str(10 * 1024 * 1024))),
            max_video_bytes=int(os.environ.get("MAX_VIDEO_BYTES", str(15 * 1024 * 1024))),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level, logging.INFO),
    )
    # python-telegram-bot is very chatty at INFO, calm it down.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
