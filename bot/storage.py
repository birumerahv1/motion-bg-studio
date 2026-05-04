"""Async SQLite storage for per-Telegram-user keys + history."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT,
    api_key TEXT NOT NULL,
    added_at INTEGER NOT NULL,
    last_used_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    mode TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    task_id TEXT,
    result_url TEXT,
    api_key_fingerprint TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, created_at DESC);
"""


@dataclass(frozen=True)
class ApiKey:
    id: int
    user_id: int
    label: str | None
    api_key: str
    added_at: int
    last_used_at: int | None


@dataclass(frozen=True)
class HistoryRow:
    id: int
    user_id: int
    created_at: int
    mode: str
    model_id: str
    prompt: str | None
    status: str
    error_message: str | None
    task_id: str | None
    result_url: str | None
    api_key_fingerprint: str | None


class Storage:
    def __init__(self, path: str) -> None:
        self._path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # ---------------- API keys ----------------

    async def add_api_key(self, user_id: int, api_key: str, label: str | None = None) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "INSERT INTO api_keys(user_id, label, api_key, added_at) VALUES (?,?,?,?)",
                (user_id, label, api_key, int(time.time())),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def list_api_keys(self, user_id: int) -> list[ApiKey]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, user_id, label, api_key, added_at, last_used_at "
                "FROM api_keys WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ) as cur:
                rows = await cur.fetchall()
        return [
            ApiKey(
                id=r["id"],
                user_id=r["user_id"],
                label=r["label"],
                api_key=r["api_key"],
                added_at=r["added_at"],
                last_used_at=r["last_used_at"],
            )
            for r in rows
        ]

    async def delete_api_key(self, user_id: int, key_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM api_keys WHERE user_id = ? AND id = ?",
                (user_id, key_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def clear_api_keys(self, user_id: int) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM api_keys WHERE user_id = ?", (user_id,)
            )
            await db.commit()
            return cur.rowcount

    async def touch_api_key(self, user_id: int, key_id: int) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE user_id = ? AND id = ?",
                (int(time.time()), user_id, key_id),
            )
            await db.commit()

    # ---------------- History ----------------

    async def insert_history(
        self,
        *,
        user_id: int,
        mode: str,
        model_id: str,
        prompt: str | None,
        status: str,
        error_message: str | None = None,
        task_id: str | None = None,
        result_url: str | None = None,
        api_key_fingerprint: str | None = None,
    ) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "INSERT INTO history(user_id, created_at, mode, model_id, prompt, status, "
                "error_message, task_id, result_url, api_key_fingerprint) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    user_id,
                    int(time.time()),
                    mode,
                    model_id,
                    prompt,
                    status,
                    error_message,
                    task_id,
                    result_url,
                    api_key_fingerprint,
                ),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def update_history(
        self,
        history_id: int,
        *,
        status: str | None = None,
        error_message: str | None = None,
        task_id: str | None = None,
        result_url: str | None = None,
        api_key_fingerprint: str | None = None,
    ) -> None:
        sets: list[str] = []
        params: list[object] = []
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if task_id is not None:
            sets.append("task_id = ?")
            params.append(task_id)
        if result_url is not None:
            sets.append("result_url = ?")
            params.append(result_url)
        if api_key_fingerprint is not None:
            sets.append("api_key_fingerprint = ?")
            params.append(api_key_fingerprint)
        if not sets:
            return
        params.append(history_id)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                f"UPDATE history SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            await db.commit()

    async def list_history(self, user_id: int, limit: int = 10) -> list[HistoryRow]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, user_id, created_at, mode, model_id, prompt, status, "
                "error_message, task_id, result_url, api_key_fingerprint "
                "FROM history WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [
            HistoryRow(
                id=r["id"],
                user_id=r["user_id"],
                created_at=r["created_at"],
                mode=r["mode"],
                model_id=r["model_id"],
                prompt=r["prompt"],
                status=r["status"],
                error_message=r["error_message"],
                task_id=r["task_id"],
                result_url=r["result_url"],
                api_key_fingerprint=r["api_key_fingerprint"],
            )
            for r in rows
        ]
