from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from api_gateway.db_live_queries import (
    build_data_lineage,
    compute_market_freshness_payload,
    fetch_latest_feature_snapshot,
    fetch_latest_signal_bundle,
    validate_live_symbol,
)


class _FakeCursor:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def fetchone(self) -> dict[str, object]:
        return self._row


class _FakeConn:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def execute(self, _sql: str, _params: tuple[object, ...]) -> _FakeCursor:
        return _FakeCursor(self._row)


def test_build_data_lineage_marks_candles_when_present() -> None:
    lineage = build_data_lineage(
        symbol="BTCUSDT",
        timeframe="1m",
        health_db="ok",
        health_redis="ok",
        candles=[{"time_s": 1}],
        latest_signal=None,
        latest_feature=None,
        latest_structure=None,
        latest_drawings=[],
        latest_news=[],
        paper_state={"open_positions": [], "last_closed_trade": None},
        online_drift={"scope": "global", "effective_action": "ok"},
    )
    candle_seg = next(s for s in lineage if s["segment_id"] == "candles")
    assert candle_seg["has_data"] is True
    assert candle_seg["why_empty_de"] == ""
    assert candle_seg.get("why_empty_en") == ""
    assert "Candles" in candle_seg["label_en"]
    sig_seg = next(s for s in lineage if s["segment_id"] == "signals")
    assert sig_seg["has_data"] is False
    assert "Signal" in sig_seg["label_de"]
    assert "Signals" in sig_seg["label_en"]
    struct_seg = next(s for s in lineage if s["segment_id"] == "structure")
    assert struct_seg["has_data"] is False
    assert struct_seg.get("diagnostic_tags") == ["producer:structure_engine"]


def test_build_data_lineage_features_tags_redis_down() -> None:
    lineage = build_data_lineage(
        symbol="BTCUSDT",
        timeframe="1m",
        health_db="ok",
        health_redis="error",
        candles=[{"time_s": 1}],
        latest_signal=None,
        latest_feature=None,
        latest_structure=None,
        latest_drawings=[],
        latest_news=[],
        paper_state={"open_positions": [], "last_closed_trade": None},
        online_drift=None,
    )
    feat = next(s for s in lineage if s["segment_id"] == "features")
    assert feat["has_data"] is False
    assert "redis_unavailable" in (feat.get("diagnostic_tags") or [])


def test_fetch_latest_feature_snapshot_formats_cost_and_liquidity_fields() -> None:
    row = {
        "canonical_instrument_id": "bitget:futures:USDT-FUTURES:BTCUSDT",
        "market_family": "futures",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "start_ts_ms": 1_700_000_000_000,
        "computed_ts_ms": 1_700_000_010_000,
        "spread_bps": 1.5,
        "bid_depth_usdt_top25": 200_000.0,
        "ask_depth_usdt_top25": 210_000.0,
        "orderbook_imbalance": -0.02,
        "depth_balance_ratio": 0.95,
        "depth_to_bar_volume_ratio": 1.2,
        "impact_buy_bps_5000": 2.1,
        "impact_sell_bps_5000": 1.9,
        "impact_buy_bps_10000": 3.3,
        "impact_sell_bps_10000": 3.1,
        "execution_cost_bps": 2.7,
        "volatility_cost_bps": 3.0,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.08,
        "open_interest": 1_000_000.0,
        "open_interest_change_pct": 2.0,
        "data_completeness_0_1": 0.92,
        "staleness_score_0_1": 0.1,
        "feature_quality_status": "ok",
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
    }
    snapshot = fetch_latest_feature_snapshot(_FakeConn(row), symbol="BTCUSDT", timeframe="5m")
    assert snapshot is not None
    assert snapshot["canonical_instrument_id"] == "bitget:futures:USDT-FUTURES:BTCUSDT"
    assert snapshot["market_family"] == "futures"
    assert snapshot["execution_cost_bps"] == 2.7
    assert snapshot["liquidity_source"] == "orderbook_levels"
    assert snapshot["feature_quality_status"] == "ok"
    assert snapshot["orderbook_age_ms"] == 2_000


def test_fetch_latest_signal_bundle_includes_regime_fields() -> None:
    row = {
        "signal_id": "00000000-0000-0000-0000-000000000001",
        "canonical_instrument_id": "bitget:futures:USDT-FUTURES:BTCUSDT",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "market_family": "futures",
        "market_regime": "breakout",
        "regime_state": "expansion",
        "regime_substate": "expansion_breakout_followthrough",
        "regime_transition_state": "stable",
        "regime_transition_reasons_json": [],
        "regime_persistence_bars": 2,
        "regime_policy_version": "1.0",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.83,
        "regime_reasons_json": ["fresh_breakout_event"],
        "signal_strength_0_100": 74.0,
        "probability_0_1": 0.68,
        "take_trade_prob": 0.74,
        "take_trade_model_version": "hgb-cal-1700000000000",
        "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
        "take_trade_calibration_method": "sigmoid",
        "expected_return_bps": 18.5,
        "expected_mae_bps": 34.0,
        "expected_mfe_bps": 62.0,
        "target_projection_models_json": [{"model_name": "expected_return_bps"}],
        "model_uncertainty_0_1": 0.26,
        "shadow_divergence_0_1": 0.06,
        "model_ood_score_0_1": 0.0,
        "model_ood_alert": False,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": [],
        "trade_action": "allow_trade",
        "decision_confidence_0_1": 0.79,
        "decision_policy_version": "hybrid-v2",
        "allowed_leverage": 14,
        "recommended_leverage": 10,
        "leverage_policy_version": "int-leverage-v1",
        "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
        "strategy_name": "BreakoutBoxStrategy",
        "playbook_id": "breakout_expansion",
        "playbook_family": "breakout",
        "playbook_decision_mode": "selected",
        "playbook_registry_version": "1.1",
        "signal_class": "gross",
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "analysis_ts_ms": 1_700_000_000_000,
        "reasons_json": [],
        "explain_short": None,
        "explain_long_md": None,
        "risk_warnings_json": [],
        "stop_explain_json": {},
        "targets_explain_json": {},
        "reward_risk_ratio": 1.8,
    }
    bundle = fetch_latest_signal_bundle(_FakeConn(row), symbol="BTCUSDT", timeframe="5m")
    assert bundle is not None
    assert bundle["canonical_instrument_id"] == "bitget:futures:USDT-FUTURES:BTCUSDT"
    assert bundle["market_family"] == "futures"
    assert bundle["market_regime"] == "breakout"
    assert bundle["regime_state"] == "expansion"
    assert bundle["regime_transition_state"] == "stable"
    assert bundle["regime_persistence_bars"] == 2
    assert bundle["regime_policy_version"] == "1.0"
    assert bundle["regime_bias"] == "long"
    assert bundle["regime_confidence_0_1"] == 0.83
    assert bundle["regime_reasons_json"] == ["fresh_breakout_event"]
    assert bundle["take_trade_prob"] == 0.74
    assert bundle["take_trade_model_version"] == "hgb-cal-1700000000000"
    assert bundle["expected_return_bps"] == 18.5
    assert bundle["expected_mae_bps"] == 34.0
    assert bundle["expected_mfe_bps"] == 62.0
    assert bundle["model_uncertainty_0_1"] == 0.26
    assert bundle["trade_action"] == "allow_trade"
    assert bundle["decision_confidence_0_1"] == 0.79
    assert bundle["decision_policy_version"] == "hybrid-v2"
    assert bundle["allowed_leverage"] == 14
    assert bundle["recommended_leverage"] == 10
    assert bundle["strategy_name"] == "BreakoutBoxStrategy"
    assert bundle["playbook_id"] == "breakout_expansion"
    assert bundle["playbook_family"] == "breakout"
    assert bundle["leverage_policy_version"] == "int-leverage-v1"
    assert bundle.get("decision_pipeline_version") is None
    assert bundle.get("decision_control_flow") is None


def test_fetch_latest_signal_bundle_decision_graph_from_reasons_json() -> None:
    dcf = {
        "pipeline_version": "se-end-decision-v4",
        "phases": [{"id": "data_quality", "order": 1, "outcome": "passed"}],
        "end_decision_binding": {"playbook_id": "x"},
    }
    row = {
        "signal_id": "00000000-0000-0000-0000-000000000002",
        "canonical_instrument_id": None,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "market_family": "futures",
        "market_regime": "trend",
        "regime_state": "trend",
        "regime_substate": None,
        "regime_transition_state": "stable",
        "regime_transition_reasons_json": [],
        "regime_persistence_bars": 1,
        "regime_policy_version": "1.0",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.7,
        "regime_reasons_json": [],
        "signal_strength_0_100": 50.0,
        "probability_0_1": 0.5,
        "take_trade_prob": 0.5,
        "take_trade_model_version": None,
        "take_trade_model_run_id": None,
        "take_trade_calibration_method": None,
        "expected_return_bps": 1.0,
        "expected_mae_bps": 1.0,
        "expected_mfe_bps": 1.0,
        "target_projection_models_json": [],
        "model_uncertainty_0_1": 0.3,
        "shadow_divergence_0_1": 0.0,
        "model_ood_score_0_1": 0.0,
        "model_ood_alert": False,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": [],
        "trade_action": "do_not_trade",
        "meta_trade_lane": None,
        "decision_confidence_0_1": 0.5,
        "decision_policy_version": "hybrid-v2",
        "allowed_leverage": 3,
        "recommended_leverage": None,
        "leverage_policy_version": "v1",
        "leverage_cap_reasons_json": [],
        "strategy_name": None,
        "playbook_id": None,
        "playbook_family": None,
        "playbook_decision_mode": "playbookless",
        "playbook_registry_version": None,
        "signal_class": "warnung",
        "decision_state": "downgraded",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "analysis_ts_ms": 1,
        "reasons_json": {"decision_control_flow": dcf},
        "explain_short": None,
        "explain_long_md": None,
        "risk_warnings_json": [],
        "stop_explain_json": {},
        "targets_explain_json": {},
        "reward_risk_ratio": None,
    }
    bundle = fetch_latest_signal_bundle(_FakeConn(row), symbol="BTCUSDT", timeframe="5m")
    assert bundle is not None
    assert bundle["decision_pipeline_version"] == "se-end-decision-v4"
    assert bundle["decision_control_flow"] == dcf


def test_validate_live_symbol_normalizes() -> None:
    assert validate_live_symbol("  btcusdt ") == "BTCUSDT"


def test_validate_live_symbol_rejects_too_short() -> None:
    with pytest.raises(ValueError, match="4..32"):
        validate_live_symbol("AB")


def test_validate_live_symbol_rejects_non_alnum() -> None:
    with pytest.raises(ValueError, match="Buchstaben"):
        validate_live_symbol("BTC-USDT")


def test_compute_market_freshness_no_candles() -> None:
    out = compute_market_freshness_payload(
        server_ts_ms=1_000_000,
        timeframe="1m",
        candle_meta=None,
        ticker_meta=None,
        stale_warn_ms=60_000,
    )
    assert out["status"] == "no_candles"


def test_compute_market_freshness_unknown_timeframe() -> None:
    out = compute_market_freshness_payload(
        server_ts_ms=1_000_000,
        timeframe="2w",
        candle_meta=None,
        ticker_meta=None,
        stale_warn_ms=60_000,
    )
    assert out["status"] == "unknown_timeframe"


def test_compute_market_freshness_live_current_bucket() -> None:
    tf_ms = 60_000
    server_ts_ms = 1_700_000_000_000
    aligned = (server_ts_ms // tf_ms) * tf_ms
    candle_meta = {"start_ts_ms": aligned, "ingest_ts_ms": server_ts_ms - 5_000}
    out = compute_market_freshness_payload(
        server_ts_ms=server_ts_ms,
        timeframe="1m",
        candle_meta=candle_meta,
        ticker_meta=None,
        stale_warn_ms=300_000,
    )
    assert out["status"] == "live"
    assert out["candle"] is not None
    assert out["candle"]["bar_lag_ms"] == 0


def test_compute_market_freshness_dead_old_bars() -> None:
    tf_ms = 60_000
    server_ts_ms = 1_700_000_000_000
    aligned = (server_ts_ms // tf_ms) * tf_ms
    old = aligned - 10 * tf_ms
    candle_meta = {"start_ts_ms": old, "ingest_ts_ms": server_ts_ms - 4_000_000}
    out = compute_market_freshness_payload(
        server_ts_ms=server_ts_ms,
        timeframe="1m",
        candle_meta=candle_meta,
        ticker_meta=None,
        stale_warn_ms=60_000,
    )
    assert out["status"] == "dead"
