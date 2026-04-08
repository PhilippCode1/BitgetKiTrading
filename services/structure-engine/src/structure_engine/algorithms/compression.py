from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Sequence

from structure_engine.algorithms.swings import Candle


def fallback_atr_pct_ratio(candles: Sequence[Candle], window: int = 14) -> float:
    """ATR/close from lokaler True-Range-SMA wenn Feature-Row fehlt."""
    if len(candles) < window + 1:
        return float("nan")
    trs: list[float] = []
    prev_close = candles[0].c
    for cur in candles[1:]:
        tr = max(cur.h - cur.l, abs(cur.h - prev_close), abs(cur.l - prev_close))
        trs.append(tr)
        prev_close = cur.c
    atr = sum(trs[-window:]) / window
    close = candles[-1].c
    if close <= 0:
        return float("nan")
    return atr / close


@dataclass(frozen=True)
class CompressionParams:
    atrp_on: float
    atrp_off: float
    range_on: float
    range_off: float


def range_20_ratio(highs: Sequence[float], lows: Sequence[float], close: float) -> float:
    if len(highs) < 20 or len(lows) < 20 or close <= 0:
        return float("nan")
    window_h = highs[-20:]
    window_l = lows[-20:]
    return (max(window_h) - min(window_l)) / close


def next_compression_state(
    prev_flag: bool,
    atr_pct_ratio: float,
    range20: float,
    range20_prev: float | None,
    params: CompressionParams,
) -> tuple[bool, str | None]:
    """
    atr_pct_ratio = atr_14 / close (not percent).
    Thresholds in .env are decimal ratios (e.g. 0.0012).
    Returns (new_compression_flag, COMPRESSION_ON|COMPRESSION_OFF|None).
    """
    if isnan(atr_pct_ratio) or isnan(range20):
        return prev_flag, None
    if prev_flag:
        if atr_pct_ratio > params.atrp_off or range20 > params.range_off:
            return False, "COMPRESSION_OFF"
        return True, None
    sinking = range20_prev is None or range20 < range20_prev
    if (
        atr_pct_ratio < params.atrp_on
        and range20 < params.range_on
        and sinking
    ):
        return True, "COMPRESSION_ON"
    return False, None


def atr_pct_ratio_from_feature(
    atr_14: float | None,
    atrp_14: float | None,
    close: float,
) -> tuple[float, bool]:
    """
    Prefer features.candle_features. atrp_14 is stored as (atr/close)*100.
    Returns (ratio, used_fallback=False) or fallback (nan, True) if unusable.
    """
    if close <= 0:
        return float("nan"), True
    if atr_14 is not None and atr_14 > 0:
        return float(atr_14) / close, False
    if atrp_14 is not None:
        return float(atrp_14) / 100.0, False
    return float("nan"), True
