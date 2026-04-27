"""Parität: ``apex_core``-Indikatoren vs. Python-Referenz (Toleranz 1e-9 wo sinnvoll)."""

from __future__ import annotations

import math
from math import isclose

import numpy as np
import pytest

from feature_engine import numeric_hotpath as nh
from feature_engine.features.atr import OHLC
from feature_engine.features.atr import atr_sma as py_atr_sma
from feature_engine.features.momentum import trend_snapshot as py_trend_snapshot
from feature_engine.features.rsi import rsi_sma as py_rsi_sma

pytest.importorskip("apex_core")


def test_numeric_hotpath_matches_python_reference_small() -> None:
    candles = [
        OHLC(10.0, 11.0, 9.5, 10.5),
        OHLC(10.5, 11.5, 10.0, 11.0),
        OHLC(11.0, 12.0, 10.8, 11.8),
        OHLC(11.8, 12.2, 11.0, 11.3),
    ]
    opens = [c.o for c in candles]
    highs = [c.h for c in candles]
    lows = [c.l for c in candles]
    closes = [c.c for c in candles]
    assert isclose(
        nh.atr_sma(candles, opens, highs, lows, closes, 3),
        py_atr_sma(candles, 3),
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_rsi_parity_monotone_series() -> None:
    closes = [100.0 + 0.1 * i for i in range(40)]
    w = 14
    assert isclose(nh.rsi_sma(closes, w), py_rsi_sma(closes, w), rel_tol=0.0, abs_tol=1e-9)


def test_trend_snapshot_parity_random_walk() -> None:
    rng = np.random.default_rng(0)
    closes = (100.0 + np.cumsum(rng.standard_normal(120))).tolist()
    rust_snap = nh.trend_snapshot(closes)
    py_snap = py_trend_snapshot(closes)
    assert isclose(rust_snap.ema_fast, py_snap.ema_fast, rel_tol=0.0, abs_tol=1e-9)
    assert isclose(rust_snap.ema_slow, py_snap.ema_slow, rel_tol=0.0, abs_tol=1e-9)
    assert isclose(rust_snap.slope_proxy, py_snap.slope_proxy, rel_tol=0.0, abs_tol=1e-9)
    assert rust_snap.trend_dir == py_snap.trend_dir


def test_ema_series_parity_numpy() -> None:
    import apex_core

    rng = np.random.default_rng(1)
    values = (10.0 + rng.standard_normal(200)).astype(np.float64)
    span = 21
    py_series = []
    alpha = 2.0 / (span + 1.0)
    cur = float(values[0])
    py_series.append(cur)
    for v in values[1:]:
        cur = alpha * float(v) + (1.0 - alpha) * cur
        py_series.append(cur)
    rs = np.asarray(apex_core.compute_ema_series(values, span), dtype=np.float64)
    assert rs.shape == values.shape
    assert np.allclose(rs, np.asarray(py_series, dtype=np.float64), rtol=0.0, atol=1e-9)


def test_atr_nan_semantics_match() -> None:
    candles = [OHLC(1.0, 2.0, 0.5, 1.5)]
    opens = [c.o for c in candles]
    highs = [c.h for c in candles]
    lows = [c.l for c in candles]
    closes = [c.c for c in candles]
    assert math.isnan(nh.atr_sma(candles, opens, highs, lows, closes, 14))
    assert math.isnan(py_atr_sma(candles, 14))
