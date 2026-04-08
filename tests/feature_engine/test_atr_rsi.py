from __future__ import annotations

import sys
from math import isclose
from pathlib import Path

import pytest

SERVICE_SRC = (
    Path(__file__).resolve().parents[2] / "services" / "feature-engine" / "src"
)
SERVICE_SRC_STR = str(SERVICE_SRC)
if SERVICE_SRC.is_dir() and SERVICE_SRC_STR not in sys.path:
    sys.path.insert(0, SERVICE_SRC_STR)

from feature_engine.features.atr import OHLC, atr_sma
from feature_engine.features.rsi import rsi_sma
from feature_engine.features.volume import volume_zscore


def test_atr_sma_matches_deterministic_reference() -> None:
    candles = [
        OHLC(10.0, 11.0, 9.5, 10.5),
        OHLC(10.5, 11.5, 10.0, 11.0),
        OHLC(11.0, 12.0, 10.8, 11.8),
        OHLC(11.8, 12.2, 11.0, 11.3),
    ]

    value = atr_sma(candles, window=3)

    assert isclose(value, 1.3, rel_tol=1e-9)


def test_rsi_returns_100_for_only_positive_closes() -> None:
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]

    value = rsi_sma(closes, window=5)

    assert isclose(value, 100.0, rel_tol=1e-9)


def test_volume_zscore_uses_previous_window_only() -> None:
    volumes = [100.0] * 50 + [150.0]

    value = volume_zscore(volumes, window=50)

    assert value == pytest.approx(0.0)
