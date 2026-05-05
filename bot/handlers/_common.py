"""Shared helpers for handlers (admin checks, fingerprint, key resolution)."""

from __future__ import annotations

import logging

from telegram.ext import ContextTypes

from ..config import Config
from ..freepik_client import fingerprint_key
from ..storage import Storage

log = logging.getLogger(__name__)


def get_storage(context: ContextTypes.DEFAULT_TYPE) -> Storage:
    return context.bot_data["storage"]


def get_config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["config"]


async def is_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    cfg = get_config(context)
    if user_id in cfg.admin_user_ids:
        return True
    storage = get_storage(context)
    return await storage.is_admin(user_id)


async def operator_keys_for(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    """Resolve the active list of operator Freepik keys.

    Combines env-provided keys with anything the admin added via
    /opaddkey. De-duplicates and filters disabled rows.
    """
    cfg = get_config(context)
    storage = get_storage(context)
    db_keys = await storage.list_operator_keys(include_disabled=False)
    seen: set[str] = set()
    out: list[str] = []
    for k in (*cfg.operator_freepik_keys, *(row.api_key for row in db_keys)):
        k = k.strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def fingerprint(api_key: str) -> str:
    return fingerprint_key(api_key)
