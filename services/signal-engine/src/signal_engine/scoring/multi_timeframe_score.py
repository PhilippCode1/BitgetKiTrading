"""
Schicht 3: Multi-Timeframe Alignment mit dokumentierten TF-Gewichten.
"""

from __future__ import annotations

from typing import Any

from signal_engine.config import DEFAULT_MTF_TF_WEIGHTS
from signal_engine.models import LayerScore, ScoringContext


def _trend_to_sign(trend_dir: str) -> int:
    if trend_dir == "UP":
        return 1
    if trend_dir == "DOWN":
        return -1
    return 0


def _feature_trend_to_sign(trend_dir_int: Any) -> int:
    try:
        v = int(trend_dir_int)
    except (TypeError, ValueError):
        return 0
    return max(-1, min(1, v))


def score_multi_timeframe(
    ctx: ScoringContext,
    *,
    primary_structure_sign: int,
) -> LayerScore:
    notes: list[str] = []
    if primary_structure_sign == 0:
        notes.append("primary_structure_neutral_mtf_limited")

    weighted = 0.0
    wsum = 0.0
    for tf, w in DEFAULT_MTF_TF_WEIGHTS.items():
        row = ctx.features_by_tf.get(tf)
        if row is None:
            notes.append(f"feature_missing_{tf}")
            continue
        sign = _feature_trend_to_sign(row.get("trend_dir"))
        if primary_structure_sign == 0:
            align = 1.0 if sign == 0 else 0.65
        else:
            if sign == primary_structure_sign:
                align = 1.0
            elif sign == 0:
                align = 0.55
            else:
                align = 0.15
        weighted += w * align
        wsum += w
        notes.append(f"tf_{tf}_sign_{sign}_align_{align:.2f}")

    if wsum <= 0:
        return LayerScore(35.0, notes + ["no_mtf_features"], ["mtf_data_missing"])

    raw = weighted / wsum
    score = max(0.0, min(100.0, raw * 100.0))
    return LayerScore(score, notes, [])
