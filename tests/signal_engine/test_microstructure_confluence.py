"""Multi-Faktor-Konfluenz: VPIN-Skalierung + Orderbuch-Druck (Rejection)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.models import ScoringContext
from signal_engine.scoring.composite_score import apply_microstructure_confluence
from signal_engine.scoring.rejection_rules import apply_rejections


def test_vpin_above_07_halves_composite_80_to_40() -> None:
    """DoD: BUY-/neutrales Signal mit Composite 80 sinkt bei hohem VPIN auf 40."""
    with (
        patch(
            "signal_engine.scoring.composite_score.read_market_vpin_score_0_1",
            return_value=0.75,
        ),
        patch(
            "signal_engine.scoring.composite_score.read_orderbook_top5_pressures_0_1",
            return_value=None,
        ),
    ):
        r = apply_microstructure_confluence(
            80.0,
            symbol="BTCUSDT",
            redis_url="redis://127.0.0.1:6379/0",
        )
    assert r.composite_pre_micro_0_100 == 80.0
    assert abs(r.composite_0_100 - 40.0) < 1e-6
    assert r.vpin_composite_scale == 0.5
    assert r.market_vpin_score_0_1 == 0.75


def test_vpin_at_07_boundary_no_scale() -> None:
    """Schwelle exklusiv: vp>0.7 (align risk_governor / live-broker)."""
    with (
        patch(
            "signal_engine.scoring.composite_score.read_market_vpin_score_0_1",
            return_value=0.7,
        ),
        patch(
            "signal_engine.scoring.composite_score.read_orderbook_top5_pressures_0_1",
            return_value=None,
        ),
    ):
        r = apply_microstructure_confluence(
            80.0,
            symbol="BTCUSDT",
            redis_url="redis://127.0.0.1:6379/0",
        )
    assert r.composite_0_100 == 80.0
    assert r.vpin_composite_scale == 1.0


def test_orderbook_ask_pressure_rejects_long(signal_settings) -> None:
    """>70 % Ask-Druck: hartes Veto gegen Long."""
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99000",
                    "price_high": "99100",
                },
                "reasons": [],
                "confidence": 50.0,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "102000",
                    "price_high": "103000",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        signal_settings,
        composite=65.0,
        structure_score=55.0,
        multi_tf_score=55.0,
        risk_score=55.0,
        proposed_direction="long",
        layer_flags=[],
        ask_pressure_0_1=0.71,
        bid_pressure_0_1=0.29,
    )
    assert r.decision_state == "rejected"
    assert "orderbook_ask_pressure_against_long" in r.rejection_reasons


def test_orderbook_bid_pressure_rejects_short(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "DOWN"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "101000",
                    "price_high": "101100",
                },
                "reasons": [],
                "confidence": 50.0,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "98000",
                    "price_high": "99000",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        signal_settings,
        composite=65.0,
        structure_score=55.0,
        multi_tf_score=55.0,
        risk_score=55.0,
        proposed_direction="short",
        layer_flags=[],
        ask_pressure_0_1=0.2,
        bid_pressure_0_1=0.8,
    )
    assert r.decision_state == "rejected"
    assert "orderbook_bid_pressure_against_short" in r.rejection_reasons
