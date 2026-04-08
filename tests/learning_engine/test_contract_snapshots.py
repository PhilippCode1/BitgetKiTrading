from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.labeling.labels import feature_snapshot_compact, signal_snapshot_compact
from shared_py.model_contracts import FEATURE_SCHEMA_HASH, MODEL_OUTPUT_SCHEMA_HASH
from shared_py.playbook_registry import PLAYBOOK_REGISTRY_VERSION


def _feature_row(timeframe: str) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000,
        "atr_14": 100.0,
        "atrp_14": 0.12,
        "rsi_14": 55.0,
        "ret_1": 0.001,
        "ret_5": 0.004,
        "momentum_score": 57.0,
        "impulse_body_ratio": 0.5,
        "impulse_upper_wick_ratio": 0.25,
        "impulse_lower_wick_ratio": 0.25,
        "range_score": 40.0,
        "trend_ema_fast": 100_200.0,
        "trend_ema_slow": 100_000.0,
        "trend_slope_proxy": 12.0,
        "trend_dir": 1,
        "confluence_score_0_100": 70.0,
        "vol_z_50": 0.3,
        "spread_bps": 1.5,
        "bid_depth_usdt_top25": 200_000.0,
        "ask_depth_usdt_top25": 210_000.0,
        "orderbook_imbalance": -0.02,
        "depth_balance_ratio": 0.95,
        "depth_to_bar_volume_ratio": 1.2,
        "impact_buy_bps_5000": 2.0,
        "impact_sell_bps_5000": 1.8,
        "impact_buy_bps_10000": 3.2,
        "impact_sell_bps_10000": 3.0,
        "execution_cost_bps": 2.6,
        "volatility_cost_bps": 2.9,
        "funding_rate": 0.0001,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.08,
        "open_interest": 1_100_000.0,
        "open_interest_change_pct": 3.5,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}",
        "computed_ts_ms": 1_700_000_010_000,
    }


def test_learning_feature_snapshot_uses_shared_contract() -> None:
    rows = {
        "1m": _feature_row("1m"),
        "5m": _feature_row("5m"),
        "15m": _feature_row("15m"),
        "1H": _feature_row("1H"),
        "4H": _feature_row("4H"),
    }
    snapshot = feature_snapshot_compact(
        primary_timeframe="5m",
        primary_feature=rows["5m"],
        features_by_tf=rows,
    )
    assert snapshot["quality_gate"]["passed"] is True
    assert snapshot["feature_schema_hash"] == FEATURE_SCHEMA_HASH
    assert snapshot["primary_tf"]["timeframe"] == "5m"
    assert snapshot["primary_tf"]["liquidity_source"] == "orderbook_levels"
    assert snapshot["timeframes"]["4H"]["timeframe"] == "4H"


def test_learning_signal_snapshot_uses_shared_output_contract() -> None:
    snapshot = signal_snapshot_compact(
        {
            "signal_id": "sig-1",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000,
            "market_regime": "trend",
            "regime_bias": "long",
            "regime_confidence_0_1": 0.82,
            "regime_reasons_json": ["structure_trend=up", "confluence_supports_trend"],
            "regime_state": "trend",
            "regime_substate": "trend_structural_alignment",
            "regime_transition_state": "stable",
            "regime_transition_reasons_json": [],
            "regime_persistence_bars": 3,
            "regime_policy_version": "1.0",
            "direction": "long",
            "signal_strength_0_100": 74.0,
            "probability_0_1": 0.73,
            "take_trade_prob": 0.79,
            "take_trade_model_version": "hgb-cal-1700000000000",
            "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
            "take_trade_calibration_method": "sigmoid",
            "expected_return_bps": 19.5,
            "expected_mae_bps": 31.0,
            "expected_mfe_bps": 57.0,
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
            "model_uncertainty_0_1": 0.22,
            "shadow_divergence_0_1": 0.05,
            "model_ood_score_0_1": 0.0,
            "model_ood_alert": False,
            "uncertainty_reasons_json": [],
            "ood_reasons_json": [],
            "abstention_reasons_json": [],
            "trade_action": "allow_trade",
            "decision_confidence_0_1": 0.82,
            "decision_policy_version": "hybrid-v2",
            "allowed_leverage": 16,
            "recommended_leverage": 10,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
            "signal_class": "gross",
            "structure_score_0_100": 71.0,
            "momentum_score_0_100": 69.0,
            "multi_timeframe_score_0_100": 72.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 63.0,
            "history_score_0_100": 52.0,
            "weighted_composite_score_0_100": 70.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted",
            "reasons_json": {"decisive_factors": ["ok"]},
            "reward_risk_ratio": 1.7,
            "expected_volatility_band": 0.11,
            "scoring_model_version": "v1.0.0",
            "playbook_id": "trend_continuation_core",
            "playbook_family": "trend_continuation",
            "playbook_decision_mode": "selected",
            "playbook_registry_version": PLAYBOOK_REGISTRY_VERSION,
        }
    )
    assert snapshot["quality_gate"]["passed"] is True
    assert snapshot["model_output_schema_hash"] == MODEL_OUTPUT_SCHEMA_HASH
    assert snapshot["market_regime"] == "trend"
    assert snapshot["regime_bias"] == "long"
    assert snapshot["direction"] == "long"
    assert snapshot["take_trade_prob"] == 0.79
    assert snapshot["playbook_id"] == "trend_continuation_core"
    assert snapshot["playbook_decision_mode"] == "selected"
    assert snapshot["take_trade_model_version"] == "hgb-cal-1700000000000"
    assert snapshot["expected_return_bps"] == 19.5
    assert snapshot["target_projection_models_json"][0]["model_name"] == "expected_return_bps"
    assert snapshot["model_uncertainty_0_1"] == 0.22
    assert snapshot["trade_action"] == "allow_trade"
    assert snapshot["decision_confidence_0_1"] == 0.82
    assert snapshot["allowed_leverage"] == 16
    assert snapshot["recommended_leverage"] == 10
