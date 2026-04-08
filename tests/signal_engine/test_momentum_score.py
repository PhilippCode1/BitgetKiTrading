from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.models import ScoringContext
from signal_engine.scoring.momentum_score import score_momentum


def test_momentum_missing_feature() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature=None,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = score_momentum(ctx)
    assert r.score <= 35.0


def test_momentum_aligned_ret1() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "momentum_score": 60.0,
            "rsi_14": 55.0,
            "ret_1": 0.002,
            "impulse_body_ratio": 0.6,
            "vol_z_50": 0.5,
        },
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = score_momentum(ctx)
    assert r.score >= 55.0


def test_momentum_uses_orderbook_imbalance_alignment() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "momentum_score": 55.0,
            "rsi_14": 55.0,
            "ret_1": 0.001,
            "impulse_body_ratio": 0.5,
            "vol_z_50": 0.2,
            "orderbook_imbalance": 0.25,
        },
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = score_momentum(ctx)
    assert r.score > 55.0
    assert "orderbook_bid_pressure_supports_uptrend" in r.notes
