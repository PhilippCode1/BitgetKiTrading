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
from signal_engine.scoring.risk_score import score_risk


def test_risk_penalizes_missing_stop() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature={"atrp_14": 0.1},
        features_by_tf={},
        drawings=[
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "101000",
                    "price_high": "102000",
                },
                "reasons": [],
                "confidence": 50.0,
            }
        ],
        news_row=None,
        last_close=100_000.0,
    )
    r = score_risk(ctx)
    assert "no_stop_drawing" in r.flags
    assert r.score < 50.0


def test_risk_higher_with_stop_and_target() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature={"atrp_14": 0.08},
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
    r = score_risk(ctx)
    assert r.score >= 55.0


def test_risk_penalizes_execution_cost_and_liquidity_fallback() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature={
            "atrp_14": 0.08,
            "spread_bps": 9.0,
            "execution_cost_bps": 20.0,
            "depth_to_bar_volume_ratio": 0.2,
            "funding_cost_bps_window": 2.0,
            "open_interest_change_pct": 10.0,
            "liquidity_source": "ticker:bitget_ws_ticker",
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
    r = score_risk(ctx)
    assert r.score < 45.0
    assert "execution_cost_elevated" in r.flags
    assert "liquidity_fallback" in r.flags


def test_risk_penalizes_shock_regime() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature={"atrp_14": 0.08},
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
    trend = score_risk(ctx, market_regime="trend", regime_bias="long")
    shock = score_risk(ctx, market_regime="shock", regime_bias="short")
    assert shock.score < trend.score
    assert "shock_regime" in shock.flags


def _ctx_with_stop_target(**kwargs: object) -> ScoringContext:
    base = dict(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature={"atrp_14": 0.08},
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
                    "price_low": "100500",
                    "price_high": "100600",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    base.update(kwargs)
    return ScoringContext(**base)  # type: ignore[arg-type]


def test_risk_regime_breakout_compression_chop() -> None:
    base = _ctx_with_stop_target()
    br = score_risk(base, market_regime="breakout")
    cp = score_risk(base, market_regime="compression")
    ch = score_risk(base, market_regime="chop")
    assert "regime_breakout_context" in br.notes
    assert "compression_regime_caution" in cp.flags
    assert "chop_regime" in ch.flags


def test_risk_neutral_bias_dings_trend() -> None:
    ctx = _ctx_with_stop_target()
    t = score_risk(ctx, market_regime="trend", regime_bias="neutral")
    assert "regime_bias_neutral" in t.notes


def test_risk_weak_reward_risk_flag() -> None:
    ctx = _ctx_with_stop_target()
    r = score_risk(ctx)
    assert "weak_reward_risk" in r.flags or "rr_missing" in r.flags


def test_risk_spread_mid_band_and_depth_ok() -> None:
    ctx = _ctx_with_stop_target(
        primary_feature={
            "atrp_14": 0.08,
            "spread_bps": 4.0,
            "depth_to_bar_volume_ratio": 1.2,
            "execution_cost_bps": 4.0,
            "funding_cost_bps_window": 0.5,
            "open_interest_change_pct": 2.0,
            "liquidity_source": "orderbook_levels",
        },
    )
    r = score_risk(ctx)
    assert "depth_vs_bar_volume_ok" in r.notes
    assert "execution_cost_ok" in r.notes


def test_risk_near_liquidity_zone() -> None:
    ctx = _ctx_with_stop_target(
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
            {
                "drawing_id": "l1",
                "type": "liquidity_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99990",
                    "price_high": "100010",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
    )
    r = score_risk(ctx)
    assert "near_liquidity_zone" in r.flags
