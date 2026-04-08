"""
Stufen von Meta-Trade-Lanes zusammenfuehren (Uncertainty vs. Hybrid/Meta).

Reihenfolge Restriktion: candidate_for_live < paper_only < shadow_only < do_not_trade
"""

from __future__ import annotations

import math

from shared_py.signal_contracts import META_TRADE_LANE_VALUES, MetaTradeLane

_LANE_RANK: dict[str, int] = {
    "candidate_for_live": 0,
    "paper_only": 1,
    "shadow_only": 2,
    "do_not_trade": 3,
}


def merge_meta_trade_lanes(
    *lanes: str | None,
    trade_action_blocked: bool = False,
) -> MetaTradeLane | None:
    """
    Gibt die restriktivste Lane zurueck. Bei blockiertem Handel immer do_not_trade.
    """
    if trade_action_blocked:
        return "do_not_trade"
    best: str | None = None
    best_rank = -1
    for raw in lanes:
        if raw is None or str(raw).strip() == "":
            continue
        lane = str(raw).strip().lower()
        if lane not in set(META_TRADE_LANE_VALUES):
            continue
        r = _LANE_RANK.get(lane, -1)
        if r > best_rank:
            best_rank = r
            best = lane
    return best  # type: ignore[return-value]


def binary_normalized_entropy_0_1(p: float) -> float:
    """Unsicherheit 0..1 aus kalibrierter Bernoulli-Wahrscheinlichkeit (Maximum bei p=0.5)."""
    x = max(1e-12, min(1.0 - 1e-12, float(p)))
    h = -(x * math.log(x) + (1.0 - x) * math.log(1.0 - x))
    return max(0.0, min(1.0, h / 0.6931471805599453))
