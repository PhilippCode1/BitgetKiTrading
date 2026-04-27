from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (SERVICE_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from shared_py.model_contracts import FEATURE_SCHEMA_HASH
from signal_engine.models import ScoringContext
from signal_engine.scoring.rejection_rules import apply_rejections
from signal_engine.service import _collect_data_quality_issues


def _feature_row(
    *, timeframe: str, computed_ts_ms: int, **overrides: object
) -> dict[str, object]:
    row: dict[str, object] = {
        "feature_schema_version": "2.0",
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": computed_ts_ms - 60_000,
        "atr_14": 120.0,
        "atrp_14": 0.12,
        "rsi_14": 55.0,
        "ret_1": 0.001,
        "ret_5": 0.003,
        "momentum_score": 58.0,
        "impulse_body_ratio": 0.5,
        "impulse_upper_wick_ratio": 0.25,
        "impulse_lower_wick_ratio": 0.25,
        "range_score": 42.0,
        "trend_ema_fast": 100_100.0,
        "trend_ema_slow": 100_000.0,
        "trend_slope_proxy": 15.0,
        "trend_dir": 1,
        "confluence_score_0_100": 75.0,
        "vol_z_50": 0.4,
        "spread_bps": 1.6,
        "bid_depth_usdt_top25": 200_000.0,
        "ask_depth_usdt_top25": 210_000.0,
        "orderbook_imbalance": -0.02,
        "depth_balance_ratio": 0.95,
        "depth_to_bar_volume_ratio": 1.2,
        "impact_buy_bps_5000": 2.1,
        "impact_sell_bps_5000": 1.9,
        "impact_buy_bps_10000": 3.4,
        "impact_sell_bps_10000": 3.1,
        "execution_cost_bps": 2.75,
        "volatility_cost_bps": 3.0,
        "funding_rate": 0.0001,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.08,
        "open_interest": 1_000_000.0,
        "open_interest_change_pct": 2.0,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}",
        "computed_ts_ms": computed_ts_ms,
    }
    row.update(overrides)
    return row


def test_collect_data_quality_flags_stale_inputs(signal_settings) -> None:
    now_ms = 1_700_000_000_000
    features = {
        "1m": _feature_row(timeframe="1m", computed_ts_ms=now_ms - 20_000),
        "5m": _feature_row(timeframe="5m", computed_ts_ms=now_ms - 400_000),
        "15m": _feature_row(timeframe="15m", computed_ts_ms=now_ms - 20_000),
        "1H": _feature_row(timeframe="1H", computed_ts_ms=now_ms - 20_000),
        "4H": _feature_row(timeframe="4H", computed_ts_ms=now_ms - 20_000),
    }
    issues = _collect_data_quality_issues(
        settings=signal_settings,
        analysis_ts_ms=now_ms,
        timeframe="5m",
        primary_feature=features["5m"],
        features_by_tf=features,
        structure_state={
            "trend_dir": "UP",
            "updated_ts_ms": now_ms - 400_000,
            "last_ts_ms": now_ms - 400_000,
        },
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99000",
                    "price_high": "99100",
                },
                "confidence": 50.0,
                "created_ts_ms": now_ms - 400_000,
                "updated_ts_ms": now_ms - 400_000,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "102000",
                    "price_high": "103000",
                },
                "confidence": 50.0,
                "created_ts_ms": now_ms - 400_000,
                "updated_ts_ms": now_ms - 400_000,
            },
        ],
        news_row={"relevance_score": 50, "published_ts_ms": now_ms - 4_000_000},
        last_close=100_000.0,
    )
    assert "stale_feature_data" in issues
    assert "stale_structure_state" in issues
    assert "stale_drawing_data" in issues
    assert "stale_news_context" in issues


def test_rejections_hard_fail_on_data_quality_issues(signal_settings) -> None:
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
        data_issues=["stale_structure_state"],
    )
    rejection = apply_rejections(
        ctx,
        signal_settings,
        composite=68.0,
        structure_score=60.0,
        multi_tf_score=60.0,
        risk_score=60.0,
        proposed_direction="long",
        layer_flags=[],
    )
    assert rejection.decision_state == "rejected"
    assert "stale_structure_state" in rejection.rejection_reasons


def test_collect_data_quality_flags_market_feature_fallbacks(signal_settings) -> None:
    now_ms = 1_700_000_000_000
    primary = _feature_row(
        timeframe="5m",
        computed_ts_ms=now_ms - 20_000,
        liquidity_source="ticker:bitget_ws_ticker",
        orderbook_age_ms=signal_settings.signal_max_orderbook_age_ms + 1,
        impact_buy_bps_5000=None,
        impact_sell_bps_5000=None,
        funding_source="missing",
        funding_rate_bps=None,
        open_interest_source="missing",
        open_interest=None,
        open_interest_change_pct=None,
    )
    features = {
        "1m": _feature_row(timeframe="1m", computed_ts_ms=now_ms - 20_000),
        "5m": primary,
    }
    issues = _collect_data_quality_issues(
        settings=signal_settings,
        analysis_ts_ms=now_ms,
        timeframe="5m",
        primary_feature=primary,
        features_by_tf=features,
        structure_state={
            "trend_dir": "UP",
            "updated_ts_ms": now_ms - 10_000,
            "last_ts_ms": now_ms - 10_000,
        },
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99000",
                    "price_high": "99100",
                },
                "confidence": 50.0,
                "created_ts_ms": now_ms - 10_000,
                "updated_ts_ms": now_ms - 10_000,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "102000",
                    "price_high": "103000",
                },
                "confidence": 50.0,
                "created_ts_ms": now_ms - 10_000,
                "updated_ts_ms": now_ms - 10_000,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    assert "liquidity_context_fallback" in issues
    assert "stale_orderbook_feature_data" in issues
    assert "missing_funding_context" in issues
    assert "missing_open_interest_context" in issues
