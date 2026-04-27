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
from signal_engine.scoring.rejection_rules import apply_rejections


def test_reject_missing_features(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature=None,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        signal_settings,
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=40.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert r.decision_state == "rejected"
    assert "missing_primary_features" in r.rejection_reasons


def test_accept_clean(signal_settings) -> None:
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
    )
    assert r.decision_state == "accepted"


def test_reject_high_execution_cost(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "computed_ts_ms": 1_700_000_000_000,
            "spread_bps": signal_settings.signal_max_spread_bps + 1.0,
            "execution_cost_bps": signal_settings.signal_max_execution_cost_bps + 1.0,
            "funding_rate_bps": signal_settings.signal_max_adverse_funding_bps + 1.0,
            "liquidity_source": "orderbook_levels",
        },
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
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert r.decision_state == "rejected"
    assert "spread_too_wide" in r.rejection_reasons


def test_rejection_disabled_short_circuits(signal_settings) -> None:
    settings = signal_settings.model_copy(update={"signal_rejection_enabled": False})
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state=None,
        structure_events=[],
        primary_feature=None,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        settings,
        composite=10.0,
        structure_score=10.0,
        multi_tf_score=10.0,
        risk_score=10.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert r.decision_state == "accepted"
    assert r.rejection_reasons == []


def test_reject_missing_structure(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state=None,
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        signal_settings,
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert "missing_structure_state" in r.rejection_reasons


def test_reject_stale_features(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1},
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        signal_settings,
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert "stale_feature_data" in r.rejection_reasons


def test_reject_adverse_funding_short(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "computed_ts_ms": 1_700_000_000_000,
            "funding_rate_bps": -(signal_settings.signal_max_adverse_funding_bps + 1.0),
            "liquidity_source": "orderbook_levels",
        },
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
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="short",
        layer_flags=[],
    )
    assert "adverse_funding_too_high" in r.rejection_reasons


def test_reject_news_shock_against_long(signal_settings) -> None:
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
        news_row={"sentiment": -0.9, "relevance_score": 80},
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
    )
    assert "news_shock_against_long" in r.rejection_reasons


def test_news_shock_skipped_when_rejection_flag_disabled(signal_settings) -> None:
    settings = signal_settings.model_copy(
        update={"signal_news_shock_rejection_enabled": False}
    )
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
        news_row={"sentiment": -0.9, "relevance_score": 80},
        last_close=100_000.0,
    )
    r = apply_rejections(
        ctx,
        settings,
        composite=65.0,
        structure_score=55.0,
        multi_tf_score=55.0,
        risk_score=55.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert "news_shock_against_long" not in r.rejection_reasons


def test_downgrade_momentum_structure_friction(signal_settings) -> None:
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
        layer_flags=["momentum_vs_structure_up"],
    )
    assert r.decision_state == "downgraded"
    assert "momentum_structure_friction" in r.rejection_reasons


def test_reject_three_soft_reasons(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "computed_ts_ms": 1_700_000_000_000,
            "liquidity_source": "orderbook_levels",
        },
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
        composite=70.0,
        structure_score=signal_settings.signal_min_structure_score_for_directional
        - 1.0,
        multi_tf_score=signal_settings.signal_min_multi_tf_score_for_directional - 1.0,
        risk_score=signal_settings.signal_min_risk_score - 1.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert r.decision_state == "rejected"
    assert len(r.rejection_reasons) >= 3


def test_reject_false_breakout_and_liquidity_fallback(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={
            "computed_ts_ms": 1_700_000_000_000,
            "liquidity_source": "ticker:x",
        },
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
        composite=70.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="long",
        layer_flags=["recent_false_breakout"],
    )
    assert "false_breakout_warning" in r.rejection_reasons
    assert "liquidity_context_fallback" in r.rejection_reasons
