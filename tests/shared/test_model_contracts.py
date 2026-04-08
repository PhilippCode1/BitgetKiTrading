from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
shared_src_str = str(SHARED_SRC)
if SHARED_SRC.is_dir() and shared_src_str not in sys.path:
    sys.path.insert(0, shared_src_str)

from shared_py.model_contracts import (
    FEATURE_SCHEMA_HASH,
    MARKET_REGIME_VALUES,
    MODEL_OUTPUT_SCHEMA_HASH,
    MODEL_TARGET_FIELDS,
    MODEL_TARGET_SCHEMA_HASH,
    REGIME_BIAS_VALUES,
    build_feature_snapshot,
    build_model_contract_bundle,
    build_model_output_snapshot,
    extract_active_models_from_signal_row,
    normalize_feature_row,
    normalize_market_regime,
    normalize_model_output_row,
)
from shared_py.playbook_registry import PLAYBOOK_REGISTRY_VERSION
from shared_py.take_trade_model import (
    TAKE_TRADE_FEATURE_SCHEMA_HASH,
    build_take_trade_feature_vector,
    take_trade_feature_contract_descriptor,
)


def _feature_row(
    *, timeframe: str, computed_ts_ms: int = 1_700_000_000_000
) -> dict[str, object]:
    return {
        "canonical_instrument_id": "bitget-futures-btcusdt",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_account_mode": "isolated",
        "instrument_metadata_snapshot_id": "snapshot-1",
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
        "spread_bps": 1.5,
        "bid_depth_usdt_top25": 250_000.0,
        "ask_depth_usdt_top25": 260_000.0,
        "orderbook_imbalance": -0.02,
        "depth_balance_ratio": 0.96,
        "depth_to_bar_volume_ratio": 1.8,
        "impact_buy_bps_5000": 2.1,
        "impact_sell_bps_5000": 1.9,
        "impact_buy_bps_10000": 3.6,
        "impact_sell_bps_10000": 3.1,
        "execution_cost_bps": 2.55,
        "volatility_cost_bps": 2.85,
        "funding_rate": 0.0001,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.1,
        "funding_time_to_next_ms": 1_800_000,
        "open_interest": 1_250_000.0,
        "open_interest_change_pct": 4.5,
        "mark_index_spread_bps": 1.4,
        "basis_bps": 2.2,
        "session_drift_bps": 18.0,
        "spread_persistence_bps": 1.8,
        "mean_reversion_pressure_0_100": 42.0,
        "breakout_compression_score_0_100": 61.0,
        "realized_vol_cluster_0_100": 57.0,
        "liquidation_distance_bps_max_leverage": 106.0,
        "data_completeness_0_1": 0.92,
        "staleness_score_0_1": 0.12,
        "gap_count_lookback": 0,
        "event_distance_ms": 1_200_000,
        "feature_quality_status": "ok",
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": "evt-1",
        "computed_ts_ms": computed_ts_ms,
    }


def test_normalize_feature_row_backfills_schema_meta_and_timeframe() -> None:
    normalized, issues = normalize_feature_row(_feature_row(timeframe="4h"))
    assert issues == []
    assert normalized is not None
    assert normalized["timeframe"] == "4H"
    assert normalized["market_family"] == "futures"
    assert normalized["canonical_instrument_id"] == "bitget-futures-btcusdt"
    assert normalized["feature_schema_hash"] == FEATURE_SCHEMA_HASH


def test_build_feature_snapshot_uses_shared_contract_across_timeframes() -> None:
    features = {
        "1m": _feature_row(timeframe="1m"),
        "5m": _feature_row(timeframe="5m"),
        "15m": _feature_row(timeframe="15m"),
        "1H": _feature_row(timeframe="1H"),
        "4H": _feature_row(timeframe="4H"),
    }
    snapshot = build_feature_snapshot(
        primary_timeframe="5m",
        primary_feature=features["5m"],
        features_by_tf=features,
    )
    assert snapshot["quality_gate"]["passed"] is True
    assert snapshot["feature_schema_hash"] == FEATURE_SCHEMA_HASH
    assert snapshot["feature_field_catalog_hash"]
    assert snapshot["primary_tf"]["timeframe"] == "5m"
    assert snapshot["primary_tf"]["mark_index_spread_bps"] == 1.4
    assert snapshot["primary_tf"]["execution_cost_bps"] == 2.55
    assert snapshot["timeframes"]["4H"]["timeframe"] == "4H"


def test_build_model_output_snapshot_and_contract_bundle_share_hashes() -> None:
    signal_snapshot = build_model_output_snapshot(
        {
            "signal_id": "sig-1",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000,
            "market_regime": "trend",
            "regime_bias": "long",
            "regime_confidence_0_1": 0.81,
            "regime_reasons_json": ["structure_trend=up", "mtf_alignment_ratio=1.00"],
            "direction": "long",
            "signal_strength_0_100": 74.0,
            "probability_0_1": 0.71,
            "take_trade_prob": 0.78,
            "take_trade_model_version": "hgb-cal-1700000000000",
            "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
            "take_trade_calibration_method": "sigmoid",
            "expected_return_bps": 21.5,
            "expected_mae_bps": 33.0,
            "expected_mfe_bps": 65.0,
            "target_projection_models_json": [
                {
                    "model_name": "expected_return_bps",
                    "version": "hgb-reg-1700000000001",
                    "run_id": "00000000-0000-4000-8000-0000000000bb",
                    "output_field": "expected_return_bps",
                    "target_field": "expected_return_bps",
                    "scaling_method": "asinh_clip",
                }
            ],
            "model_uncertainty_0_1": 0.18,
            "shadow_divergence_0_1": 0.07,
            "model_ood_score_0_1": 0.0,
            "model_ood_alert": False,
            "uncertainty_reasons_json": [],
            "ood_reasons_json": [],
            "abstention_reasons_json": [],
            "trade_action": "allow_trade",
            "decision_confidence_0_1": 0.86,
            "decision_policy_version": "hybrid-v2",
            "allowed_leverage": 18,
            "recommended_leverage": 10,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
            "signal_class": "gross",
            "structure_score_0_100": 70.0,
            "momentum_score_0_100": 68.0,
            "multi_timeframe_score_0_100": 72.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 62.0,
            "history_score_0_100": 51.0,
            "weighted_composite_score_0_100": 69.5,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted",
            "reasons_json": {"decisive_factors": ["ok"]},
            "reward_risk_ratio": 1.8,
            "expected_volatility_band": 0.11,
            "scoring_model_version": "v1.0.0",
            "playbook_id": "trend_continuation_core",
            "playbook_family": "trend_continuation",
            "playbook_decision_mode": "selected",
            "playbook_registry_version": PLAYBOOK_REGISTRY_VERSION,
        }
    )
    contract_bundle = build_model_contract_bundle(
        active_models=extract_active_models_from_signal_row(signal_snapshot)
    )
    assert signal_snapshot["quality_gate"]["passed"] is True
    assert signal_snapshot["model_output_schema_hash"] == MODEL_OUTPUT_SCHEMA_HASH
    assert contract_bundle["feature_snapshot"]["schema_hash"] == FEATURE_SCHEMA_HASH
    assert contract_bundle["model_output"]["schema_hash"] == MODEL_OUTPUT_SCHEMA_HASH
    assert contract_bundle["targets"]["schema_hash"] == MODEL_TARGET_SCHEMA_HASH
    assert contract_bundle["playbook_registry"]["registry_version"] == PLAYBOOK_REGISTRY_VERSION
    assert contract_bundle["active_models"][0]["model_name"] == "take_trade_prob"
    assert contract_bundle["active_models"][1]["model_name"] == "expected_return_bps"
    assert contract_bundle["targets"]["fields"] == list(MODEL_TARGET_FIELDS)
    assert "take_trade_label" in contract_bundle["targets"]["fields"]
    assert "expected_return_bps" in contract_bundle["targets"]["fields"]
    assert "liquidation_risk" in contract_bundle["targets"]["fields"]


def test_model_contract_bundle_merges_target_labeling_audit() -> None:
    audit = {"target_evaluation_contract_version": "1.0", "evaluation_window": {"decision_ts_ms": 1}}
    bundle = build_model_contract_bundle(target_labeling_audit=audit)
    assert bundle["target_labeling"] == audit
    bare = build_model_contract_bundle()
    assert "target_labeling" not in bare


def test_normalize_model_output_row_normalizes_regime_aliases() -> None:
    normalized, issues = normalize_model_output_row(
        {
            "signal_id": "sig-1",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000,
            "market_regime": "UP",
            "regime_bias": None,
            "regime_confidence_0_1": 0.7,
            "regime_reasons_json": ["legacy_up"],
            "direction": "long",
            "signal_strength_0_100": 70.0,
            "probability_0_1": 0.68,
            "take_trade_prob": 0.74,
            "take_trade_model_version": "hgb-cal-1700000000000",
            "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
            "take_trade_calibration_method": "sigmoid",
            "expected_return_bps": 18.0,
            "expected_mae_bps": 28.0,
            "expected_mfe_bps": 49.0,
            "target_projection_models_json": [
                {
                    "model_name": "expected_mfe_bps",
                    "version": "hgb-reg-1700000000002",
                    "run_id": "00000000-0000-4000-8000-0000000000cc",
                    "output_field": "expected_mfe_bps",
                    "target_field": "expected_mfe_bps",
                    "scaling_method": "log1p_clip",
                }
            ],
            "model_uncertainty_0_1": 0.41,
            "shadow_divergence_0_1": 0.06,
            "model_ood_score_0_1": 0.0,
            "model_ood_alert": False,
            "uncertainty_reasons_json": ["regime_uncertain"],
            "ood_reasons_json": [],
            "abstention_reasons_json": [],
            "trade_action": "allow_trade",
            "decision_confidence_0_1": 0.72,
            "decision_policy_version": "hybrid-v2",
            "allowed_leverage": 9,
            "recommended_leverage": 7,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": ["model_cap_binding", "depth_factor_cap"],
            "signal_class": "kern",
            "structure_score_0_100": 66.0,
            "momentum_score_0_100": 61.0,
            "multi_timeframe_score_0_100": 63.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 59.0,
            "history_score_0_100": 52.0,
            "weighted_composite_score_0_100": 64.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted",
            "reasons_json": {"decisive_factors": ["ok"]},
            "reward_risk_ratio": 1.8,
            "expected_volatility_band": 0.11,
            "scoring_model_version": "v1.0.0",
            "playbook_id": "trend_continuation_core",
            "playbook_family": "trend_continuation",
            "playbook_decision_mode": "selected",
            "playbook_registry_version": PLAYBOOK_REGISTRY_VERSION,
        }
    )
    assert issues == []
    assert normalized is not None
    assert normalized["market_regime"] == "trend"
    assert normalized["regime_bias"] == "long"
    assert normalized["regime_confidence_0_1"] == 0.7
    assert normalized["regime_reasons_json"] == ["legacy_up"]
    assert normalized["expected_return_bps"] == 18.0
    assert (
        normalized["target_projection_models_json"][0]["model_name"]
        == "expected_mfe_bps"
    )
    assert normalized["model_uncertainty_0_1"] == 0.41
    assert normalized["trade_action"] == "allow_trade"
    assert normalized["decision_confidence_0_1"] == 0.72
    assert normalized["allowed_leverage"] == 9
    assert normalized["recommended_leverage"] == 7
    assert normalized["leverage_policy_version"] == "int-leverage-v1"
    assert normalized["playbook_id"] == "trend_continuation_core"
    assert normalized["playbook_family"] == "trend_continuation"
    assert normalized["playbook_decision_mode"] == "selected"
    assert set(MARKET_REGIME_VALUES) == {
        "trend",
        "chop",
        "compression",
        "breakout",
        "shock",
        "dislocation",
    }
    assert set(REGIME_BIAS_VALUES) == {"long", "short", "neutral"}
    assert normalize_market_regime("RANGE") == "chop"


def test_normalize_model_output_flags_invalid_calibration_and_leverage_range() -> None:
    base = {
        "signal_id": "sig-cal",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "analysis_ts_ms": 1_700_000_000_000,
        "market_regime": "trend",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.7,
        "direction": "long",
        "signal_class": "kern",
        "signal_strength_0_100": 70.0,
        "probability_0_1": 0.68,
        "take_trade_prob": 0.74,
        "take_trade_model_version": "v-test",
        "take_trade_model_run_id": "00000000-0000-4000-8000-000000000001",
        "take_trade_calibration_method": "platt",
        "expected_return_bps": 10.0,
        "expected_mae_bps": 20.0,
        "expected_mfe_bps": 30.0,
        "model_uncertainty_0_1": 0.2,
        "trade_action": "allow_trade",
        "decision_state": "accepted",
        "rejection_state": False,
        "allowed_leverage": 76,
        "recommended_leverage": 6,
    }
    _norm, issues = normalize_model_output_row(base)
    assert "take_trade_calibration_method_invalid" in issues
    assert "allowed_leverage_out_of_range" in issues
    assert "recommended_leverage_out_of_range" in issues


def test_take_trade_feature_vector_includes_regime_and_contract_hashes() -> None:
    signal_row = {
        "signal_id": "sig-1",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "analysis_ts_ms": 1_700_000_000_000,
        "market_regime": "breakout",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.88,
        "direction": "long",
        "signal_strength_0_100": 74.0,
        "probability_0_1": 0.71,
        "signal_class": "gross",
        "structure_score_0_100": 70.0,
        "momentum_score_0_100": 68.0,
        "multi_timeframe_score_0_100": 72.0,
        "news_score_0_100": 50.0,
        "risk_score_0_100": 62.0,
        "history_score_0_100": 51.0,
        "weighted_composite_score_0_100": 69.5,
        "rejection_state": False,
        "rejection_reasons_json": [],
        "decision_state": "accepted",
        "reasons_json": {},
        "reward_risk_ratio": 1.8,
        "expected_volatility_band": 0.11,
        "scoring_model_version": "v1.0.0",
    }
    features = {
        "1m": _feature_row(timeframe="1m"),
        "5m": _feature_row(timeframe="5m"),
        "15m": _feature_row(timeframe="15m"),
        "1H": _feature_row(timeframe="1H"),
        "4H": _feature_row(timeframe="4H"),
    }
    feature_snapshot = build_feature_snapshot(
        primary_timeframe="5m",
        primary_feature=features["5m"],
        features_by_tf=features,
    )
    vector = build_take_trade_feature_vector(
        signal_row=signal_row,
        feature_snapshot=feature_snapshot,
    )
    contract = take_trade_feature_contract_descriptor()
    assert contract["schema_hash"] == TAKE_TRADE_FEATURE_SCHEMA_HASH
    assert vector["heuristic_probability_0_1"] == 0.71
    assert vector["market_regime_is_breakout"] == 1.0
    assert vector["regime_bias_is_long"] == 1.0
    assert vector["timeframe_is_5m"] == 1.0
