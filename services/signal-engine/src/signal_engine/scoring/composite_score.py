"""
Gewichteter Composite-Score (Rohergebnis vor Rejection).
"""

from __future__ import annotations


def weighted_composite(
    structure: float,
    momentum: float,
    multi_tf: float,
    news: float,
    risk: float,
    history: float,
    weights: tuple[float, float, float, float, float, float],
) -> float:
    w_s, w_m, w_mt, w_n, w_r, w_h = weights
    raw = (
        structure * w_s
        + momentum * w_m
        + multi_tf * w_mt
        + news * w_n
        + risk * w_r
        + history * w_h
    )
    return max(0.0, min(100.0, raw))
