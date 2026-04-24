from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVICE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (SERVICE_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from signal_engine.hybrid_decision import HYBRID_DECISION_POLICY_VERSION, assess_hybrid_decision


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()


def test_hybrid_decision_allows_strong_trade(signal_settings) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            signal_class="gross",
            take_trade_prob=0.81,
            expected_return_bps=18.0,
            expected_mae_bps=20.0,
            expected_mfe_bps=34.0,
            model_uncertainty_0_1=0.14,
        ),
    )
    assert result["trade_action"] == "allow_trade"
    assert result["decision_state"] == "accepted"
    assert result["meta_trade_lane"] == "candidate_for_live"
    assert result["decision_policy_version"] == HYBRID_DECISION_POLICY_VERSION
    assert result["decision_confidence_0_1"] >= 0.55
    assert result["allowed_leverage"] >= result["recommended_leverage"] >= 7
    assert result["leverage_policy_version"] == "int-leverage-v1"


def test_hybrid_decision_blocks_negative_edge(signal_settings) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            signal_class="kern",
            take_trade_prob=0.51,
            expected_return_bps=2.0,
            expected_mae_bps=28.0,
            expected_mfe_bps=20.0,
            model_uncertainty_0_1=0.18,
        ),
    )
    assert result["trade_action"] == "do_not_trade"
    assert result["decision_state"] == "downgraded"
    assert result["meta_trade_lane"] == "do_not_trade"
    assert "hybrid_take_trade_prob_below_minimum" in result["abstention_reasons_json"]
    assert result["recommended_leverage"] is None


def test_hybrid_decision_preserves_safety_abstention(signal_settings) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            decision_state="rejected",
            trade_action="do_not_trade",
            signal_class="warnung",
            abstention_reasons_json=["uncertainty_above_threshold"],
            take_trade_prob=0.95,
            expected_return_bps=45.0,
            expected_mae_bps=15.0,
            expected_mfe_bps=55.0,
            model_uncertainty_0_1=0.82,
        ),
    )
    assert result["trade_action"] == "do_not_trade"
    assert result["decision_state"] == "rejected"
    assert result["meta_trade_lane"] == "do_not_trade"
    assert "uncertainty_above_threshold" in result["abstention_reasons_json"]
    assert "hybrid_prior_do_not_trade" in result["abstention_reasons_json"]


def test_hybrid_meta_lane_shadow_downgrades_execution(signal_settings) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            market_regime="shock",
            take_trade_prob=0.81,
            expected_return_bps=18.0,
            expected_mae_bps=20.0,
            expected_mfe_bps=34.0,
            model_uncertainty_0_1=0.14,
        ),
    )
    assert result["meta_trade_lane"] == "shadow_only"
    assert result["trade_action"] == "do_not_trade"
    assert result["decision_state"] == "downgraded"
    assert "meta_lane_shadow_stress_regime" in result["abstention_reasons_json"]


def test_hybrid_meta_lane_paper_allows_trade(signal_settings) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            risk_score_0_100=40.0,
            take_trade_prob=0.74,
            expected_return_bps=16.0,
            expected_mae_bps=24.0,
            expected_mfe_bps=34.0,
            model_uncertainty_0_1=0.20,
        ),
    )
    assert result["meta_trade_lane"] == "paper_only"
    assert result["trade_action"] == "allow_trade"
    assert "meta_lane_paper_risk_score" in result["abstention_reasons_json"]


def test_hybrid_decision_abstains_when_allowed_leverage_falls_below_minimum(
    signal_settings,
) -> None:
    result = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            expected_return_bps=14.0,
            expected_mae_bps=18.0,
            expected_mfe_bps=30.0,
            source_snapshot_json={
                "feature_snapshot": {
                    "primary_tf": {
                        "spread_bps": 12.0,
                        "execution_cost_bps": 24.0,
                        "volatility_cost_bps": 18.0,
                        "funding_rate_bps": 8.0,
                        "funding_cost_bps_window": 7.0,
                        "depth_to_bar_volume_ratio": 0.15,
                        "impact_buy_bps_10000": 18.0,
                        "impact_sell_bps_10000": 18.0,
                        "liquidity_source": "fallback",
                    }
                },
                "quality_gate": {"passed": False},
                "data_issues": ["orderbook_missing"],
            },
        ),
    )
    assert result["trade_action"] == "do_not_trade"
    assert result["decision_state"] == "downgraded"
    assert result["allowed_leverage"] < 7
    assert "hybrid_allowed_leverage_below_minimum" in result["abstention_reasons_json"]


def _signal_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "direction": "long",
        "market_regime": "trend",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.82,
        "signal_strength_0_100": 74.0,
        "weighted_composite_score_0_100": 72.0,
        "probability_0_1": 0.71,
        "take_trade_prob": 0.74,
        "expected_return_bps": 16.0,
        "expected_mae_bps": 24.0,
        "expected_mfe_bps": 34.0,
        "model_uncertainty_0_1": 0.20,
        "trade_action": "allow_trade",
        "decision_state": "accepted",
        "rejection_state": False,
        "signal_class": "kern",
        "abstention_reasons_json": [],
        "expected_volatility_band": 0.08,
        "source_snapshot_json": {
            "feature_snapshot": {
                "primary_tf": {
                    "spread_bps": 1.2,
                    "execution_cost_bps": 2.8,
                    "volatility_cost_bps": 2.6,
                    "funding_rate_bps": 0.8,
                    "funding_cost_bps_window": 0.2,
                    "depth_to_bar_volume_ratio": 1.6,
                    "impact_buy_bps_10000": 3.2,
                    "impact_sell_bps_10000": 3.4,
                    "liquidity_source": "orderbook_levels",
                    "atrp_14": 0.08,
                }
            },
            "quality_gate": {"passed": True},
            "data_issues": [],
        },
    }
    row.update(overrides)
    return row
