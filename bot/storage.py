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

-- Operator-shared Freepik keys, used for paid users (the bot itself, not BYO).
CREATE TABLE IF NOT EXISTS operator_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    api_key TEXT NOT NULL,
    added_at INTEGER NOT NULL,
    last_used_at INTEGER,
    disabled INTEGER NOT NULL DEFAULT 0
);

-- One row per Telegram user. Plan defaults to 'free'.
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    plan_id TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    quota_used INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL
);

-- Pending / approved / rejected payments awaiting admin review.
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id TEXT NOT NULL,
    amount_idr INTEGER NOT NULL,
    status TEXT NOT NULL,        -- pending | approved | rejected | cancelled
    reference_code TEXT NOT NULL,
    proof_file_id TEXT,          -- Telegram file_id of bukti screenshot
    proof_message_id INTEGER,    -- so admin can reply with one tap
    proof_caption TEXT,
    created_at INTEGER NOT NULL,
    reviewed_at INTEGER,
    reviewed_by INTEGER,         -- admin telegram user_id
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(reference_code);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    added_at INTEGER NOT NULL,
    note TEXT
);

-- Free-form key/value store for QRIS image, bank info, support handle, etc.
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Cache for /me display so users see who they are by Telegram name.
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_seen_at INTEGER NOT NULL
);
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


@dataclass(frozen=True)
class OperatorKey:
    id: int
    label: str | None
    api_key: str
    added_at: int
    last_used_at: int | None
    disabled: bool


@dataclass(frozen=True)
class Subscription:
    user_id: int
    plan_id: str
    started_at: int
    expires_at: int
    quota_used: int
    updated_at: int


@dataclass(frozen=True)
class Payment:
    id: int
    user_id: int
    plan_id: str
    amount_idr: int
    status: str
    reference_code: str
    proof_file_id: str | None
    proof_message_id: int | None
    proof_caption: str | None
    created_at: int
    reviewed_at: int | None
    reviewed_by: int | None
    rejection_reason: str | None


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

    # ---------------- Operator (shared) Freepik keys ----------------

    async def add_operator_key(self, api_key: str, label: str | None = None) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "INSERT INTO operator_keys(label, api_key, added_at) VALUES (?,?,?)",
                (label, api_key, int(time.time())),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def list_operator_keys(self, include_disabled: bool = False) -> list[OperatorKey]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            sql = (
                "SELECT id, label, api_key, added_at, last_used_at, disabled "
                "FROM operator_keys "
            )
            if not include_disabled:
                sql += "WHERE disabled = 0 "
            sql += "ORDER BY id ASC"
            async with db.execute(sql) as cur:
                rows = await cur.fetchall()
        return [
            OperatorKey(
                id=r["id"],
                label=r["label"],
                api_key=r["api_key"],
                added_at=r["added_at"],
                last_used_at=r["last_used_at"],
                disabled=bool(r["disabled"]),
            )
            for r in rows
        ]

    async def delete_operator_key(self, key_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM operator_keys WHERE id = ?", (key_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    async def set_operator_key_disabled(self, key_id: int, disabled: bool) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "UPDATE operator_keys SET disabled = ? WHERE id = ?",
                (1 if disabled else 0, key_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def touch_operator_key(self, key_id: int) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE operator_keys SET last_used_at = ? WHERE id = ?",
                (int(time.time()), key_id),
            )
            await db.commit()

    # ---------------- Subscriptions ----------------

    async def get_subscription(self, user_id: int) -> Subscription | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, plan_id, started_at, expires_at, quota_used, "
                "updated_at FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ) as cur:
                r = await cur.fetchone()
        if r is None:
            return None
        return Subscription(
            user_id=r["user_id"],
            plan_id=r["plan_id"],
            started_at=r["started_at"],
            expires_at=r["expires_at"],
            quota_used=r["quota_used"],
            updated_at=r["updated_at"],
        )

    async def upsert_subscription(
        self,
        *,
        user_id: int,
        plan_id: str,
        started_at: int,
        expires_at: int,
        quota_used: int = 0,
    ) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT INTO subscriptions(
                    user_id, plan_id, started_at, expires_at, quota_used, updated_at
                ) VALUES (?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    started_at = excluded.started_at,
                    expires_at = excluded.expires_at,
                    quota_used = excluded.quota_used,
                    updated_at = excluded.updated_at
                """,
                (user_id, plan_id, started_at, expires_at, quota_used, now),
            )
            await db.commit()

    async def increment_quota(self, user_id: int, by: int) -> int:
        """Increment quota_used by `by` and return the new value."""
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE subscriptions SET quota_used = quota_used + ?, updated_at = ? "
                "WHERE user_id = ?",
                (by, now, user_id),
            )
            await db.commit()
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT quota_used FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ) as cur:
                r = await cur.fetchone()
        return int(r["quota_used"]) if r else 0

    # ---------------- Payments ----------------

    async def insert_payment(
        self,
        *,
        user_id: int,
        plan_id: str,
        amount_idr: int,
        reference_code: str,
    ) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "INSERT INTO payments(user_id, plan_id, amount_idr, status, "
                "reference_code, created_at) VALUES (?,?,?,?,?,?)",
                (
                    user_id,
                    plan_id,
                    amount_idr,
                    "pending",
                    reference_code,
                    int(time.time()),
                ),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def attach_payment_proof(
        self,
        payment_id: int,
        *,
        file_id: str,
        message_id: int,
        caption: str | None,
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE payments SET proof_file_id = ?, proof_message_id = ?, "
                "proof_caption = ? WHERE id = ?",
                (file_id, message_id, caption, payment_id),
            )
            await db.commit()

    async def set_payment_status(
        self,
        payment_id: int,
        status: str,
        *,
        reviewed_by: int | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE payments SET status = ?, reviewed_at = ?, reviewed_by = ?, "
                "rejection_reason = ? WHERE id = ?",
                (
                    status,
                    int(time.time()),
                    reviewed_by,
                    rejection_reason,
                    payment_id,
                ),
            )
            await db.commit()

    async def get_payment(self, payment_id: int) -> Payment | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM payments WHERE id = ?", (payment_id,)
            ) as cur:
                r = await cur.fetchone()
        if r is None:
            return None
        return _payment_from_row(r)

    async def list_payments(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        limit: int = 25,
    ) -> list[Payment]:
        sql = "SELECT * FROM payments WHERE 1=1 "
        params: list[object] = []
        if user_id is not None:
            sql += "AND user_id = ? "
            params.append(user_id)
        if status is not None:
            sql += "AND status = ? "
            params.append(status)
        sql += "ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        return [_payment_from_row(r) for r in rows]

    async def find_pending_payment_by_ref(self, reference_code: str) -> Payment | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM payments WHERE reference_code = ? AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (reference_code,),
            ) as cur:
                r = await cur.fetchone()
        return _payment_from_row(r) if r else None

    async def find_latest_pending_payment(self, user_id: int) -> Payment | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM payments WHERE user_id = ? AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ) as cur:
                r = await cur.fetchone()
        return _payment_from_row(r) if r else None

    # ---------------- Admins ----------------

    async def add_admin(self, user_id: int, note: str | None = None) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO admins(user_id, added_at, note) VALUES (?,?,?)",
                (user_id, int(time.time()), note),
            )
            await db.commit()

    async def remove_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM admins WHERE user_id = ?", (user_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    async def list_admins(self) -> list[int]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id FROM admins ORDER BY user_id ASC"
            ) as cur:
                rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows]

    async def is_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            async with db.execute(
                "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
            ) as cur:
                r = await cur.fetchone()
        return r is not None

    # ---------------- Settings ----------------

    async def get_setting(self, key: str) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cur:
                r = await cur.fetchone()
        return r["value"] if r else None

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, int(time.time())),
            )
            await db.commit()

    async def delete_setting(self, key: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("DELETE FROM settings WHERE key = ?", (key,))
            await db.commit()

    # ---------------- Users ----------------

    async def upsert_user(
        self,
        *,
        user_id: int,
        username: str | None,
        first_name: str | None,
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO users(user_id, username, first_name, last_seen_at) "
                "VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
                "username = excluded.username, first_name = excluded.first_name, "
                "last_seen_at = excluded.last_seen_at",
                (user_id, username, first_name, int(time.time())),
            )
            await db.commit()

    async def list_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id FROM users ORDER BY user_id ASC"
            ) as cur:
                rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows]

    async def get_user_label(self, user_id: int) -> str:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT username, first_name FROM users WHERE user_id = ?",
                (user_id,),
            ) as cur:
                r = await cur.fetchone()
        if r is None:
            return f"id:{user_id}"
        if r["username"]:
            return f"@{r['username']}"
        if r["first_name"]:
            return f"{r['first_name']} (id:{user_id})"
        return f"id:{user_id}"

    # ---------------- History helpers used by free tier ----------------

    async def count_history_since(
        self,
        user_id: int,
        since_ts: int,
        *,
        statuses: tuple[str, ...] = ("COMPLETED", "DONE", "SUCCESS", "SUCCEEDED"),
    ) -> int:
        placeholders = ",".join("?" for _ in statuses)
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT COUNT(*) AS n FROM history "
                f"WHERE user_id = ? AND created_at >= ? AND status IN ({placeholders})",
                (user_id, since_ts, *statuses),
            ) as cur:
                r = await cur.fetchone()
        return int(r["n"]) if r else 0


def _payment_from_row(r) -> Payment:  # noqa: ANN001 -- aiosqlite.Row
    return Payment(
        id=r["id"],
        user_id=r["user_id"],
        plan_id=r["plan_id"],
        amount_idr=r["amount_idr"],
        status=r["status"],
        reference_code=r["reference_code"],
        proof_file_id=r["proof_file_id"],
        proof_message_id=r["proof_message_id"],
        proof_caption=r["proof_caption"],
        created_at=r["created_at"],
        reviewed_at=r["reviewed_at"],
        reviewed_by=r["reviewed_by"],
        rejection_reason=r["rejection_reason"],
    )
