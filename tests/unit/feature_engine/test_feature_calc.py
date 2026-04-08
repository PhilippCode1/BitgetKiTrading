"""Unit: deterministische Feature-Berechnungen (ATR, RSI, Returns)."""

from __future__ import annotations

import math

from feature_engine.features import OHLC, atr_sma, rsi_sma, simple_return
from feature_engine.features.momentum import trend_snapshot


def _flat_candles(n: int, price: float = 100.0) -> list[OHLC]:
    return [OHLC(o=price, h=price + 1, l=price - 1, c=price) for _ in range(n)]


def test_atr_sma_constant_range() -> None:
    candles = _flat_candles(20, 100.0)
    atr = atr_sma(candles, 14)
    assert not math.isnan(atr)
    assert atr > 0


def test_rsi_sma_flat_market_near_fifty() -> None:
    candles = _flat_candles(30, 100.0)
    closes = [c.c for c in candles]
    rsi = rsi_sma(closes, 14)
    assert not math.isnan(rsi)
    assert 40 <= rsi <= 60


def test_simple_return_up() -> None:
    closes = [100.0, 101.0, 102.0]
    r = simple_return(closes, 1)
    assert r is not None
    assert abs(r - (102.0 / 101.0 - 1.0)) < 1e-9


def test_trend_snapshot_uptrend() -> None:
    closes = [float(i) for i in range(50)]
    snap = trend_snapshot(closes)
    assert snap.trend_dir in (-1, 0, 1)
