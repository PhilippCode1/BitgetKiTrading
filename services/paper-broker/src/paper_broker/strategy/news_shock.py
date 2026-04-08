from __future__ import annotations

from decimal import Decimal
from typing import Literal

ImpactAction = Literal["none", "partial", "full"]


def _is_immediate(impact_window: str) -> bool:
    w = (impact_window or "").strip().lower()
    return w in ("immediate", "sofort", "instant")


def sentiment_opposes_position(sentiment: str, position_side: str) -> bool:
    s = (sentiment or "").strip().lower()
    side = position_side.strip().lower()
    bear = ("bear", "baer", "bärisch", "short")
    bull = ("bull", "bullish", "long")
    is_bear = any(x in s for x in bear)
    is_bull = any(x in s for x in bull)
    if side == "long" and is_bear:
        return True
    if side == "short" and is_bull:
        return True
    return False


def evaluate_news_shock(
    *,
    relevance_score: int,
    sentiment: str,
    impact_window: str,
    position_side: str,
    shock_threshold: int,
    partial_pct: Decimal,
) -> tuple[bool, ImpactAction, str]:
    if not _is_immediate(impact_window):
        return False, "none", "impact_not_immediate"
    if relevance_score < shock_threshold:
        return False, "none", "below_threshold"
    if not sentiment_opposes_position(sentiment, position_side):
        return False, "none", "sentiment_not_opposed"
    if partial_pct >= Decimal("1") or partial_pct <= Decimal("0"):
        return True, "full", "news_shock_full"
    return True, "partial", "news_shock_partial"
