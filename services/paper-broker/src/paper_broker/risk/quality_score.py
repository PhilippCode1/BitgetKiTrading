from __future__ import annotations

from decimal import Decimal
from typing import Any

from paper_broker.config import PaperBrokerSettings


def compute_stop_quality(
    *,
    entry: Decimal,
    side: str,
    stop_price: Decimal,
    atr: Decimal,
    stop_plan: dict[str, Any],
    tp_plan: dict[str, Any],
    atrp: Decimal | None,
    settings: PaperBrokerSettings,
) -> tuple[int, list[str]]:
    score = 100
    warnings: list[str] = []
    s = side.lower()
    if s == "long":
        dist = entry - stop_price
    else:
        dist = stop_price - entry
    if atr > 0:
        min_dist = atr * Decimal(str(settings.stop_min_atr_mult))
        if dist < min_dist:
            score -= 30
            warnings.append("stop_tighter_than_min_atr_mult")

    liq = stop_plan.get("liquidity_basis") or {}
    db = liq.get("distance_bps")
    if db is not None:
        try:
            if Decimal(str(db)) < Decimal(str(settings.liq_stop_avoid_bps)):
                score -= 20
                warnings.append("stop_near_liquidity_cluster")
        except Exception:
            pass

    rr = estimate_rr(entry, side, stop_price, tp_plan)
    if rr is not None and rr < Decimal(str(settings.min_rr_for_trade)):
        score -= 20
        warnings.append("rr_below_min")

    if atrp is not None and atrp > Decimal("0.02"):
        score -= 10
        warnings.append("high_atrp_noisy")

    score = max(0, min(100, score))
    return score, warnings


def estimate_rr(entry: Decimal, side: str, stop_price: Decimal, tp_plan: dict[str, Any]) -> Decimal | None:
    tgs = tp_plan.get("targets") or []
    if not tgs:
        return None
    try:
        tp1 = Decimal(str(tgs[0]["target_price"]))
    except Exception:
        return None
    s = side.lower()
    if s == "long":
        risk = entry - stop_price
        rew = tp1 - entry
    else:
        risk = stop_price - entry
        rew = entry - tp1
    if risk <= 0:
        return None
    return rew / risk
