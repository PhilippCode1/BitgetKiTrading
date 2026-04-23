"""Numerische Hotpaths: ATR/RSI/Trend bevorzugt über ``apex_core`` (Rust), sonst Python."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from feature_engine.features.atr import OHLC, atr_sma as _py_atr_sma
from feature_engine.features.momentum import TrendSnapshot, trend_snapshot as _py_trend_snapshot
from feature_engine.features.rsi import rsi_sma as _py_rsi_sma

try:
    import apex_core as _apex_core  # type: ignore[import-not-found]
except ImportError:
    _apex_core = None


def apex_core_available() -> bool:
    return _apex_core is not None


def _as_f64_c(a: Sequence[float]) -> np.ndarray:
    return np.asarray(a, dtype=np.float64, order="C")


def atr_sma(ohlc: Sequence[OHLC], opens: Sequence[float], highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], window: int) -> float:
    if _apex_core is not None:
        return float(
            _apex_core.compute_atr_sma(
                _as_f64_c(opens),
                _as_f64_c(highs),
                _as_f64_c(lows),
                _as_f64_c(closes),
                int(window),
            )
        )
    return float(_py_atr_sma(ohlc, int(window)))


def rsi_sma(closes: Sequence[float], window: int) -> float:
    if _apex_core is not None:
        return float(_apex_core.compute_rsi_sma(_as_f64_c(closes), int(window)))
    return float(_py_rsi_sma(closes, int(window)))


def trend_snapshot(
    closes: Sequence[float],
    *,
    fast_window: int = 12,
    slow_window: int = 26,
    slope_lookback: int = 3,
) -> TrendSnapshot:
    if _apex_core is not None:
        ema_fast, ema_slow, slope_proxy, trend_dir = _apex_core.compute_trend_snapshot(
            _as_f64_c(closes),
            int(fast_window),
            int(slow_window),
            int(slope_lookback),
        )
        return TrendSnapshot(
            ema_fast=float(ema_fast),
            ema_slow=float(ema_slow),
            slope_proxy=float(slope_proxy),
            trend_dir=int(trend_dir),
        )
    return _py_trend_snapshot(
        closes,
        fast_window=int(fast_window),
        slow_window=int(slow_window),
        slope_lookback=int(slope_lookback),
    )
