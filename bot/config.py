"""Bot configuration from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    freepik_base: str
    poll_interval_seconds: float
    max_image_bytes: int
    max_video_bytes: int
    log_level: str
    # Operator-shared Freepik keys (for paid SaaS mode). Bot also picks up
    # additional keys from the operator_keys table via /opaddkey.
    operator_freepik_keys: tuple[str, ...]
    # Initial admin Telegram user IDs. After bootstrap, admins can be
    # managed at runtime via /setadmin / /unsetadmin.
    admin_user_ids: tuple[int, ...]
    # If True, anyone can /addkey their own Freepik key and use it. Default
    # False since the user picked the operator-key SaaS model.
    allow_byo_keys: bool

    @classmethod
    def from_env(cls) -> Config:
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Get one from @BotFather and export it as an "
                "environment variable, or put it in a .env file next to bot/."
            )
        admin_ids: list[int] = []
        for raw in _split_csv(os.environ.get("ADMIN_USER_IDS", "")):
            try:
                admin_ids.append(int(raw))
            except ValueError:
                logging.getLogger(__name__).warning(
                    "Ignoring non-integer admin id: %r", raw
                )
        operator_keys = tuple(_split_csv(os.environ.get("OPERATOR_FREEPIK_KEYS", "")))
        return cls(
            bot_token=token,
            db_path=os.environ.get("DB_PATH", "bot/data/bot.db"),
            freepik_base=os.environ.get("FREEPIK_BASE", "https://api.freepik.com"),
            poll_interval_seconds=float(os.environ.get("POLL_INTERVAL", "4")),
            max_image_bytes=int(os.environ.get("MAX_IMAGE_BYTES", str(10 * 1024 * 1024))),
            max_video_bytes=int(os.environ.get("MAX_VIDEO_BYTES", str(15 * 1024 * 1024))),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            operator_freepik_keys=operator_keys,
            admin_user_ids=tuple(admin_ids),
            allow_byo_keys=os.environ.get("ALLOW_BYO_KEYS", "0").strip() in ("1", "true", "yes"),
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
