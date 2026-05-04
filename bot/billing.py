"""Subscription plans, quota math, and per-generation cost mapping.

Edit the `PLANS` dict in this file to tweak prices, quotas, and cost
weights. The bot will pick up changes on next restart. You can also
override individual values at runtime via the admin commands
(`/setplan` and friends).
"""

from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass

from .freepik_models import get_model

# Granted period for a paid plan, in seconds.
SUBSCRIPTION_PERIOD_SECONDS: int = 30 * 24 * 60 * 60  # 30 days

# Free-tier quotas evaluate against a rolling 24-hour window. We use the
# `subscriptions` row with plan_id="free" so the same quota_used /
# expires_at columns work; expires_at for free is now+24h.
FREE_PERIOD_SECONDS: int = 24 * 60 * 60

# A "credit" is the unit deducted from a subscription. Each generation
# costs N credits depending on its mode/duration. Edit the function
# `cost_for_generation` below to retune.


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_idr: int  # 0 = free
    quota: int  # credits per period (per_seconds below)
    period_seconds: int
    description: str
    paid: bool
    sort: int

    @property
    def price_label(self) -> str:
        if self.price_idr <= 0:
            return "Gratis"
        return f"Rp {self.price_idr:,}".replace(",", ".") + " / bulan"

    @property
    def short_label(self) -> str:
        if self.price_idr <= 0:
            return f"{self.name} • {self.quota}/hari"
        return f"{self.name} • {self.quota} credit/bln • Rp {self.price_idr:,}".replace(
            ",", "."
        )


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_idr=0,
        quota=3,
        period_seconds=FREE_PERIOD_SECONDS,
        description=(
            "Coba gratis: 3 generasi gambar / hari. Video dan motion control "
            "tidak tersedia di tier ini."
        ),
        paid=False,
        sort=0,
    ),
    "basic": Plan(
        id="basic",
        name="Basic",
        price_idr=49_000,
        quota=100,
        period_seconds=SUBSCRIPTION_PERIOD_SECONDS,
        description=(
            "100 credits / bulan. Cocok untuk hobi & test. Akses semua model "
            "image; video pendek juga ok (tiap video 3-5 credits)."
        ),
        paid=True,
        sort=1,
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_idr=149_000,
        quota=500,
        period_seconds=SUBSCRIPTION_PERIOD_SECONDS,
        description=(
            "500 credits / bulan. Untuk creator aktif. Akses penuh semua "
            "model termasuk Veo 3.1, Kling 3 Pro, Seedance 1080p."
        ),
        paid=True,
        sort=2,
    ),
    "unlimited": Plan(
        id="unlimited",
        name="Unlimited",
        price_idr=499_000,
        quota=5_000,
        period_seconds=SUBSCRIPTION_PERIOD_SECONDS,
        description=(
            "5.000 credits / bulan. Untuk produksi tinggi / agency. Pasti "
            "lebih dari cukup untuk pemakaian normal."
        ),
        paid=True,
        sort=3,
    ),
}


def get_plan(plan_id: str) -> Plan | None:
    return PLANS.get(plan_id)


def paid_plans() -> list[Plan]:
    return [p for p in PLANS.values() if p.paid and p.price_idr > 0]


def cost_for_generation(model_id: str, duration: int | None) -> int:
    """Return the credit cost for a single generation.

    Defaults:
      * image: 1 credit
      * video <=5s: 3 credits
      * video >5s: 5 credits
      * motion-control: 4 credits
    """
    model = get_model(model_id)
    if model is None:
        return 1
    if model.mode in ("text-to-image",):
        return 1
    if model.mode == "motion-control":
        return 4
    # video mode: text-to-video / image-to-video
    if duration is None or duration <= 5:
        return 3
    return 5


def is_video_model(model_id: str) -> bool:
    model = get_model(model_id)
    if model is None:
        return False
    return model.mode in ("text-to-video", "image-to-video", "motion-control")


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
class QuotaCheck:
    ok: bool
    reason: str | None  # human-readable error if not ok
    plan: Plan
    remaining: int  # remaining credits in current period (0 if expired)
    expires_at: int  # 0 if no active subscription


def evaluate_quota(
    *,
    plan_id: str,
    quota_used: int,
    expires_at: int,
    cost: int,
    now: int | None = None,
) -> QuotaCheck:
    """Decide whether a generation is allowed."""
    now = now if now is not None else now_ts()
    plan = PLANS.get(plan_id) or PLANS["free"]

    if plan.paid:
        if expires_at <= now:
            return QuotaCheck(
                ok=False,
                reason=(
                    f"Langganan *{plan.name}* sudah habis. "
                    "Beli ulang dengan /buy."
                ),
                plan=plan,
                remaining=0,
                expires_at=expires_at,
            )
    # For free tier, expires_at is rolling 24h window — if it has elapsed,
    # caller should reset quota_used before evaluating. We do not reset here.
    remaining = max(0, plan.quota - quota_used)
    if remaining < cost:
        return QuotaCheck(
            ok=False,
            reason=(
                f"Quota tidak cukup. Sisa {remaining} dari {plan.quota} "
                f"credits, generasi ini butuh {cost} credits. "
                "Beli paket lebih besar dengan /buy."
            ),
            plan=plan,
            remaining=remaining,
            expires_at=expires_at,
        )
    return QuotaCheck(
        ok=True,
        reason=None,
        plan=plan,
        remaining=remaining - cost,
        expires_at=expires_at,
    )
