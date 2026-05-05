"""Subscription plans (no quota / credit system).

Two plans only:
  * Bulanan: Rp 49.999 / 30 hari, akses unlimited
  * Lifetime: Rp 499.999 sekali bayar, akses unlimited selamanya

Edit `PLANS` below to tweak prices and durations.
"""

from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass

# Period for the monthly plan, in seconds.
MONTHLY_PERIOD_SECONDS: int = 30 * 24 * 60 * 60  # 30 days

# Effective "forever" for the lifetime plan, in seconds (~100 years).
LIFETIME_PERIOD_SECONDS: int = 100 * 365 * 24 * 60 * 60

# Backwards-compat aliases (other modules import this name).
SUBSCRIPTION_PERIOD_SECONDS: int = MONTHLY_PERIOD_SECONDS


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_idr: int
    period_seconds: int
    description: str
    sort: int
    lifetime: bool = False

    # Kept for compat with older callers; always paid in this build.
    @property
    def paid(self) -> bool:  # noqa: D401
        return True

    @property
    def price_label(self) -> str:
        if self.lifetime:
            return f"Rp {self.price_idr:,}".replace(",", ".") + " (sekali bayar)"
        return f"Rp {self.price_idr:,}".replace(",", ".") + " / bulan"

    @property
    def period_label(self) -> str:
        if self.lifetime:
            return "selamanya"
        days = self.period_seconds // (24 * 3600)
        return f"{days} hari"


PLANS: dict[str, Plan] = {
    "monthly": Plan(
        id="monthly",
        name="Bulanan",
        price_idr=49_999,
        period_seconds=MONTHLY_PERIOD_SECONDS,
        description=(
            "Akses unlimited semua model (Text→Image, Text→Video, Image→Video, "
            "Motion Control) selama 30 hari."
        ),
        sort=1,
    ),
    "lifetime": Plan(
        id="lifetime",
        name="Lifetime",
        price_idr=499_999,
        period_seconds=LIFETIME_PERIOD_SECONDS,
        description=(
            "Bayar sekali, akses unlimited selamanya. Semua model, semua mode, "
            "tanpa batas waktu."
        ),
        sort=2,
        lifetime=True,
    ),
}


def get_plan(plan_id: str) -> Plan | None:
    return PLANS.get(plan_id)


def paid_plans() -> list[Plan]:
    """All purchasable plans, sorted by price."""
    return sorted(PLANS.values(), key=lambda p: p.sort)


def make_reference_code(user_id: int) -> str:
    """Short, user-readable transfer reference code."""
    suffix = "".join(secrets.choice(string.digits) for _ in range(4))
    return f"FP-{user_id % 100000:05d}-{suffix}"


def now_ts() -> int:
    return int(time.time())


def humanize_seconds_until(target_ts: int, *, now: int | None = None) -> str:
    now = now if now is not None else now_ts()
    delta = target_ts - now
    if delta <= 0:
        return "habis"
    # Lifetime threshold: if more than 5 years remaining, just say "selamanya".
    if delta > 5 * 365 * 24 * 3600:
        return "selamanya"
    days, rem = divmod(delta, 24 * 3600)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days >= 1:
        return f"{days}h {hours}j"
    if hours >= 1:
        return f"{hours}j {minutes}m"
    return f"{minutes}m"


def format_idr(amount: int) -> str:
    return "Rp " + f"{amount:,}".replace(",", ".")


@dataclass(frozen=True)
class SubscriptionCheck:
    ok: bool
    reason: str | None
    plan: Plan | None
    expires_at: int  # 0 if no subscription


def is_subscription_active(
    *,
    plan_id: str | None,
    expires_at: int,
    now: int | None = None,
) -> SubscriptionCheck:
    """Return whether this user can generate right now.

    No quota / credit math — just an active-window check. Unknown plan_id
    is treated as "active subscription with no metadata" as long as the
    expiry hasn't passed (so legacy plan ids still work).
    """
    now = now if now is not None else now_ts()
    if not plan_id:
        return SubscriptionCheck(
            ok=False,
            reason=(
                "Belum ada langganan aktif.\n"
                "Ketik /buy untuk pilih paket — Bulanan Rp 49.999 atau "
                "Lifetime Rp 499.999."
            ),
            plan=None,
            expires_at=0,
        )
    plan = PLANS.get(plan_id)
    if expires_at <= now:
        plan_name = plan.name if plan else plan_id
        return SubscriptionCheck(
            ok=False,
            reason=(
                f"Langganan *{plan_name}* sudah habis. "
                "Perpanjang dengan /buy."
            ),
            plan=plan,
            expires_at=expires_at,
        )
    return SubscriptionCheck(ok=True, reason=None, plan=plan, expires_at=expires_at)
