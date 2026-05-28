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
from signal_engine.scoring.regime_classifier import classify_market_regime


def test_classify_compression_regime() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={
            "trend_dir": "UP",
            "compression_flag": True,
            "breakout_box_json": {"prebreak_side": "high"},
        },
        structure_events=[],
        primary_feature={
            "range_score": 82.0,
            "atrp_14": 0.04,
            "vol_z_50": 0.2,
        },
        features_by_tf={
            "15m": {"trend_dir": 1},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 1},
        },
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    regime = classify_market_regime(ctx)
    assert regime.market_regime == "compression"
    assert regime.regime_state == "compression"
    assert regime.regime_bias == "long"
    assert regime.regime_confidence_0_1 >= 0.7


def test_classify_breakout_regime() -> None:
    analysis_ts_ms = 1_700_000_000_000
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=analysis_ts_ms,
        structure_state={
            "trend_dir": "UP",
            "compression_flag": False,
            "breakout_box_json": {},
        },
        structure_events=[
            {
                "type": "BREAKOUT",
                "ts_ms": analysis_ts_ms - 60_000,
                "details_json": {"side": "UP"},
            }
        ],
        primary_feature={
            "range_score": 48.0,
            "atrp_14": 0.08,
            "vol_z_50": 0.9,
            "impulse_body_ratio": 0.7,
            "confluence_score_0_100": 71.0,
        },
        features_by_tf={
            "15m": {"trend_dir": 1},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 1},
        },
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    regime = classify_market_regime(ctx)
    assert regime.market_regime == "breakout"
    assert regime.regime_state == "expansion"
    assert regime.regime_bias == "long"
    assert "fresh_breakout_event" in regime.regime_reasons_json


def test_classify_shock_regime_from_news_and_dislocation() -> None:
    analysis_ts_ms = 1_700_000_000_000
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=analysis_ts_ms,
        structure_state={
            "trend_dir": "DOWN",
            "compression_flag": False,
            "breakout_box_json": {},
        },
        structure_events=[],
        primary_feature={
            "range_score": 35.0,
            "atrp_14": 0.22,
            "vol_z_50": 2.4,
            "spread_bps": 14.0,
            "execution_cost_bps": 26.0,
            "open_interest_change_pct": 12.0,
            "volatility_cost_bps": 15.0,
        },
        features_by_tf={
            "15m": {"trend_dir": -1},
            "1H": {"trend_dir": -1},
            "4H": {"trend_dir": -1},
        },
        drawings=[],
        news_row={
            "relevance_score": 82.0,
            "sentiment": "bearish",
            "impact_window": "immediate",
        },
        last_close=100_000.0,
    )
    regime = classify_market_regime(ctx)
    assert regime.market_regime == "shock"
    assert regime.regime_state == "shock"
    assert regime.regime_bias == "short"
    assert regime.regime_confidence_0_1 >= 0.8
    assert regime.regime_snapshot.get("regime_engine_version")
    assert regime.regime_snapshot.get("regime_substate")


def test_classify_dislocation_regime_without_news() -> None:
    analysis_ts_ms = 1_700_000_000_000
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=analysis_ts_ms,
        structure_state={
            "trend_dir": "RANGE",
            "compression_flag": False,
            "breakout_box_json": {},
        },
        structure_events=[],
        primary_feature={
            "vol_z_50": 2.2,
            "atrp_14": 0.20,
            "spread_bps": 12.0,
        },
        features_by_tf={
            "15m": {"trend_dir": 0},
            "1H": {"trend_dir": 0},
            "4H": {"trend_dir": 0},
        },
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    regime = classify_market_regime(ctx)
    assert regime.market_regime == "dislocation"
    assert regime.regime_state == "low_liquidity"


def test_classify_chop_on_false_breakout_noise() -> None:
    analysis_ts_ms = 1_700_000_000_000
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=analysis_ts_ms,
        structure_state={
            "trend_dir": "RANGE",
            "compression_flag": False,
            "breakout_box_json": {},
        },
        structure_events=[
            {
                "type": "FALSE_BREAKOUT",
                "ts_ms": analysis_ts_ms - 120_000,
                "details_json": {"side": "UP"},
            }
        ],
        primary_feature={"range_score": 62.0, "atrp_14": 0.09},
        features_by_tf={
            "15m": {"trend_dir": 0},
            "1H": {"trend_dir": 0},
            "4H": {"trend_dir": 0},
        },
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    regime = classify_market_regime(ctx)
    assert regime.market_regime == "chop"
    assert regime.regime_state in {
        "mean_reverting",
        "range_grind",
        "session_transition",
    }
    assert "recent_false_breakout" in regime.regime_reasons_json
