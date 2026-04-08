from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Sequence


@dataclass(frozen=True)
class CandleImpulse:
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float


@dataclass(frozen=True)
class TrendSnapshot:
    ema_fast: float
    ema_slow: float
    slope_proxy: float
    trend_dir: int


def simple_return(closes: Sequence[float], bars: int) -> float:
    if bars <= 0 or len(closes) < bars + 1:
        return float("nan")
    base = closes[-1 - bars]
    if base == 0.0:
        return float("nan")
    return (closes[-1] / base) - 1.0


def momentum_score(ret_1: float, ret_5: float) -> float:
    if isnan(ret_1) and isnan(ret_5):
        return float("nan")
    effective_ret_1 = 0.0 if isnan(ret_1) else ret_1
    effective_ret_5 = 0.0 if isnan(ret_5) else ret_5
    score = (effective_ret_1 * 0.35 + effective_ret_5 * 0.65) * 10_000.0
    return max(-100.0, min(100.0, score))


def candle_impulse(o: float, h: float, l: float, c: float) -> CandleImpulse:
    candle_range = max(h - l, 0.0)
    if candle_range == 0.0:
        return CandleImpulse(body_ratio=0.0, upper_wick_ratio=0.0, lower_wick_ratio=0.0)
    body = abs(c - o)
    upper_wick = max(h - max(o, c), 0.0)
    lower_wick = max(min(o, c) - l, 0.0)
    return CandleImpulse(
        body_ratio=body / candle_range,
        upper_wick_ratio=upper_wick / candle_range,
        lower_wick_ratio=lower_wick / candle_range,
    )


def ema(values: Sequence[float], span: int) -> float:
    if not values:
        return float("nan")
    alpha = 2.0 / (span + 1.0)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def trend_snapshot(
    closes: Sequence[float],
    *,
    fast_window: int = 12,
    slow_window: int = 26,
    slope_lookback: int = 3,
) -> TrendSnapshot:
    if not closes:
        return TrendSnapshot(
            ema_fast=float("nan"),
            ema_slow=float("nan"),
            slope_proxy=float("nan"),
            trend_dir=0,
        )
    fast_series = _ema_series(closes, fast_window)
    slow_series = _ema_series(closes, slow_window)
    ema_fast = fast_series[-1]
    ema_slow = slow_series[-1]
    if len(fast_series) > slope_lookback:
        slope_proxy = ema_fast - fast_series[-1 - slope_lookback]
    elif len(fast_series) >= 2:
        slope_proxy = ema_fast - fast_series[-2]
    else:
        slope_proxy = 0.0
    if ema_fast > ema_slow and slope_proxy > 0.0:
        trend_dir = 1
    elif ema_fast < ema_slow and slope_proxy < 0.0:
        trend_dir = -1
    else:
        trend_dir = 0
    return TrendSnapshot(
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        slope_proxy=slope_proxy,
        trend_dir=trend_dir,
    )


def range_score(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    ema_fast: float,
    ema_slow: float,
    window: int = 20,
) -> float:
    if not closes or not highs or not lows:
        return float("nan")
    lookback = min(window, len(closes), len(highs), len(lows))
    recent_high = max(highs[-lookback:])
    recent_low = min(lows[-lookback:])
    span = recent_high - recent_low
    if span <= 0.0:
        return 100.0
    center = (recent_high + recent_low) / 2.0
    distance_to_center = abs(closes[-1] - center) / span
    ema_separation = abs(ema_fast - ema_slow) / span
    compression = min(1.0, ema_separation)
    balance = min(1.0, distance_to_center * 2.0)
    score = 100.0 * (1.0 - min(1.0, compression * 0.6 + balance * 0.4))
    return max(0.0, min(100.0, score))


def _ema_series(values: Sequence[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (span + 1.0)
    current = values[0]
    series = [current]
    for value in values[1:]:
        current = alpha * value + (1.0 - alpha) * current
        series.append(current)
    return series
