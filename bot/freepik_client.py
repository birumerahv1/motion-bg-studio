"""Freepik async client with multi-API-key auto-failover.

Mirrors the behaviour of `web/lib/freepik.ts` + `web/app/api/generate/route.ts`:
on auth (401/403), rate limit (429), or server (5xx) failure for one key, the
client transparently retries against the next key in the list. 4xx errors
that won't be fixed by rotation (e.g. 400 from a malformed prompt) are
returned to the caller so the bot can surface them.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FreepikResult:
    ok: bool
    status: int
    data: Any | None
    error_message: str | None
    api_key_index: int | None
    api_key_fingerprint: str | None


def fingerprint_key(key: str) -> str:
    """Non-reversible short hash + last 4 chars; safe to log/display."""
    h = 5381
    for ch in key:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}:{key[-4:]}"


def _redact(s: str, head: int = 3, tail: int = 3) -> str:
    if len(s) <= head + tail:
        return "•" * len(s)
    return f"{s[:head]}…{s[-tail:]}"


class FreepikClient:
    def __init__(
        self,
        base: str = "https://api.freepik.com",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base = base.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def call(
        self,
        method: str,
        path: str,
        api_keys: list[str],
        *,
        json_body: dict | None = None,
        preferred_index: int | None = None,
    ) -> FreepikResult:
        if not api_keys:
            return FreepikResult(
                ok=False,
                status=0,
                data=None,
                error_message="no_api_keys_configured",
                api_key_index=None,
                api_key_fingerprint=None,
            )

        order: list[int] = []
        if (
            preferred_index is not None
            and 0 <= preferred_index < len(api_keys)
        ):
            order.append(preferred_index)
        for i in range(len(api_keys)):
            if i not in order:
                order.append(i)

        last_error = "all_keys_failed"
        last_status = 0

        for idx in order:
            key = api_keys[idx]
            if not key:
                continue
            headers = {
                "x-freepik-api-key": key,
                "Accept": "application/json",
            }
            try:
                resp = await self._client.request(
                    method,
                    f"{self._base}{path}",
                    json=json_body if method.upper() == "POST" else None,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                last_error = f"network_error:{exc!s}"
                logger.warning(
                    "freepik request failed for key#%d (%s): %s",
                    idx + 1,
                    _redact(fingerprint_key(key)),
                    exc,
                )
                continue

            last_status = resp.status_code

            # auth / rate / 5xx → try next key
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                snippet = (resp.text or "")[:200]
                last_error = (
                    f"key_{idx + 1}_failed:{resp.status_code}:{snippet}"
                )
                logger.info(
                    "rotating away from key#%d (%s): %d",
                    idx + 1,
                    fingerprint_key(key),
                    resp.status_code,
                )
                continue

            try:
                data: Any | None = resp.json()
            except ValueError:
                data = None

            return FreepikResult(
                ok=resp.is_success,
                status=resp.status_code,
                data=data,
                error_message=None if resp.is_success else f"freepik_{resp.status_code}",
                api_key_index=idx,
                api_key_fingerprint=fingerprint_key(key),
            )

        return FreepikResult(
            ok=False,
            status=last_status,
            data=None,
            error_message=last_error,
            api_key_index=None,
            api_key_fingerprint=None,
        )


def parse_status(task_data: Any) -> str | None:
    """Extract a normalized task status from a GET-task response.

    Different endpoints nest the status differently — sometimes at top
    level, sometimes under `data.status` or `task.status`. We probe every
    plausible shape and uppercase the result.
    """
    if not isinstance(task_data, dict):
        return None

    candidates: list[Any] = [
        task_data.get("status"),
        task_data.get("state"),
    ]
    nested = task_data.get("data")
    if isinstance(nested, dict):
        candidates.append(nested.get("status"))
        candidates.append(nested.get("state"))
    nested = task_data.get("task")
    if isinstance(nested, dict):
        candidates.append(nested.get("status"))

    for c in candidates:
        if isinstance(c, str) and c:
            return c.upper()
    return None


def extract_task_id(post_data: Any) -> str | None:
    """Pull the task ID out of the POST response.

    Freepik commonly returns either `{"data": {"task_id": "..."}}` or
    `{"task_id": "..."}` or just `{"id": "..."}`. We try them in order.
    """
    if not isinstance(post_data, dict):
        return None
    for key in ("task_id", "id"):
        v = post_data.get(key)
        if isinstance(v, str) and v:
            return v
    nested = post_data.get("data")
    if isinstance(nested, dict):
        for key in ("task_id", "id"):
            v = nested.get(key)
            if isinstance(v, str) and v:
                return v
    return None


async def poll_until_done(
    client: FreepikClient,
    task_base_path: str,
    task_id: str,
    api_keys: list[str],
    *,
    interval_seconds: float = 4.0,
    on_tick: Callable[[str, Any], Awaitable[None]] | None = None,
    cancel_event: asyncio.Event | None = None,
) -> FreepikResult:
    """Poll GET {task_base_path}/{task_id} until status is terminal.

    Terminal statuses: COMPLETED, FAILED, CANCELED, ERROR.
    The caller controls cancellation via `cancel_event` — when set, polling
    stops immediately and a synthetic CANCELED FreepikResult is returned.
    """
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return FreepikResult(
                ok=False,
                status=0,
                data=None,
                error_message="cancelled_by_user",
                api_key_index=None,
                api_key_fingerprint=None,
            )

        result = await client.call(
            "GET",
            f"{task_base_path}/{task_id}",
            api_keys,
        )
        if not result.ok:
            return result

        status = parse_status(result.data) or ""
        if on_tick is not None:
            await on_tick(status, result.data)
        if status in ("COMPLETED", "DONE", "SUCCESS", "SUCCEEDED"):
            return result
        if status in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
            return FreepikResult(
                ok=False,
                status=result.status,
                data=result.data,
                error_message=f"task_{status.lower()}",
                api_key_index=result.api_key_index,
                api_key_fingerprint=result.api_key_fingerprint,
            )

        try:
            await asyncio.wait_for(
                cancel_event.wait() if cancel_event else asyncio.sleep(interval_seconds),
                timeout=interval_seconds,
            )
        except asyncio.TimeoutError:
            pass
