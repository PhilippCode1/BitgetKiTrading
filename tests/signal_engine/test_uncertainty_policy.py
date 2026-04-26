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

from deterministic_signal_payloads import (  # noqa: E402
    base_allow_trade_signal,
    take_trade_prediction_low_uncertainty,
    target_projection_complete,
)

from signal_engine.models import ScoringContext  # noqa: E402
from signal_engine.uncertainty import assess_model_uncertainty  # noqa: E402


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()


def test_uncertainty_hard_abstain_on_high_ood_score_without_alert(signal_settings) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row={
            "market_regime": "trend",
            "regime_confidence_0_1": 0.88,
            "probability_0_1": 0.72,
        },
        take_trade_prediction={
            "take_trade_prob": 0.74,
            "take_trade_calibration_method": "isotonic",
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.48,
                "ood_score_0_1": 0.90,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection={
            "expected_return_bps": 14.0,
            "expected_mae_bps": 18.0,
            "expected_mfe_bps": 31.0,
            "target_projection_diagnostics": {
                "ood_score_0_1": 0.20,
                "ood_alert": False,
                "ood_reasons_json": [],
                "max_bound_proximity_0_1": 0.12,
            },
        },
    )
    assert assessment["trade_action"] == "do_not_trade"
    assert "ood_score_hard_abstain" in assessment["abstention_reasons_json"]


def test_uncertainty_policy_abstains_on_ood_alert(signal_settings) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row={
            "market_regime": "trend",
            "regime_confidence_0_1": 0.88,
            "probability_0_1": 0.72,
        },
        take_trade_prediction={
            "take_trade_prob": 0.74,
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.48,
                "ood_score_0_1": 0.91,
                "ood_alert": True,
                "ood_reasons_json": ["ood_feature:funding_rate_bps"],
            },
        },
        target_projection={
            "expected_return_bps": 14.0,
            "expected_mae_bps": 18.0,
            "expected_mfe_bps": 31.0,
            "target_projection_diagnostics": {
                "ood_score_0_1": 0.20,
                "ood_alert": False,
                "ood_reasons_json": [],
                "max_bound_proximity_0_1": 0.12,
            },
        },
    )
    assert assessment["trade_action"] == "do_not_trade"
    assert "model_ood_alert" in assessment["abstention_reasons_json"]
    assert assessment["model_ood_alert"] is True


def test_uncertainty_policy_abstains_on_shadow_model_divergence(
    signal_settings,
) -> None:
    tight = signal_settings.model_copy(
        update={
            "model_shadow_divergence_threshold": 0.05,
            "model_max_uncertainty": 0.10,
        }
    )
    row = base_allow_trade_signal()
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=tight,
        signal_row=row,
        take_trade_prediction=take_trade_prediction_low_uncertainty(
            take_trade_prob=0.15
        ),
        target_projection=target_projection_complete(),
    )
    assert "shadow_divergence_high" in assessment["uncertainty_reasons_json"]
    assert assessment["trade_action"] == "do_not_trade"
    assert "uncertainty_above_threshold" in assessment["abstention_reasons_json"]


def test_uncertainty_policy_abstains_on_missing_take_trade_prob(
    signal_settings,
) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row=base_allow_trade_signal(),
        take_trade_prediction={
            "take_trade_prob": None,
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.5,
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection=target_projection_complete(),
    )
    assert "missing_take_trade_prediction" in assessment["abstention_reasons_json"]
    assert assessment["trade_action"] == "do_not_trade"


def test_uncertainty_missing_projection_and_ood_reason_filter(
    signal_settings,
) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row={
            "market_regime": "compression",
            "regime_confidence_0_1": 0.5,
            "probability_0_1": 0.6,
        },
        take_trade_prediction={
            "take_trade_prob": 0.6,
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.9,
                "ood_score_0_1": 0.15,
                "ood_alert": False,
                "ood_reasons_json": [123, "ood_note"],
            },
        },
        target_projection={
            "expected_return_bps": None,
            "expected_mae_bps": 1.0,
            "expected_mfe_bps": 2.0,
            "target_projection_diagnostics": {
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
    )
    assert "missing_target_projection_output" in assessment["uncertainty_reasons_json"]
    assert "ood_note" in assessment["uncertainty_reasons_json"]


def test_uncertainty_chop_regime_and_missing_shadow_baseline(
    signal_settings,
) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row={
            "market_regime": "chop",
            "regime_confidence_0_1": 0.9,
        },
        take_trade_prediction={
            "take_trade_prob": 0.5,
            "take_trade_model_diagnostics": {"confidence_0_1": 0.85},
        },
        target_projection={
            "expected_return_bps": 1.0,
            "expected_mae_bps": 2.0,
            "expected_mfe_bps": 3.0,
            "target_projection_diagnostics": {"max_bound_proximity_0_1": 0.1},
        },
    )
    assert "missing_shadow_baseline" in assessment["uncertainty_reasons_json"]


def test_uncertainty_shadow_lane_allows_trade_with_relaxed_thresholds(
    signal_settings,
) -> None:
    relaxed = signal_settings.model_copy(
        update={
            "model_max_uncertainty": 0.99,
            "model_uncertainty_shadow_lane": 0.01,
            "model_uncertainty_paper_lane": 0.005,
            "model_ood_hard_abstain_score": 0.99,
            "model_ood_shadow_lane_score": 0.99,
            "model_ood_paper_lane_score": 0.98,
            "model_shadow_divergence_hard_abstain": 0.99,
            "model_shadow_divergence_shadow_lane": 0.01,
        }
    )
    row = base_allow_trade_signal()
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=relaxed,
        signal_row=row,
        take_trade_prediction=take_trade_prediction_low_uncertainty(take_trade_prob=0.60),
        target_projection=target_projection_complete(),
    )
    assert assessment["trade_action"] == "allow_trade"
    assert assessment["uncertainty_execution_lane"] == "shadow_only"
    assert assessment["uncertainty_gate_phase"] == "shadow_only"
    assert assessment["abstention_reasons_json"] == []


def test_uncertainty_abstains_when_calibration_required_but_missing(
    signal_settings,
) -> None:
    strict_cal = signal_settings.model_copy(update={"model_calibration_required": True})
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=strict_cal,
        signal_row=base_allow_trade_signal(),
        take_trade_prediction={
            "take_trade_prob": 0.71,
            "take_trade_calibration_method": None,
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.6,
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection=target_projection_complete(),
    )
    assert assessment["trade_action"] == "do_not_trade"
    assert "take_trade_calibration_missing_when_required" in assessment["abstention_reasons_json"]


def test_uncertainty_policy_abstains_on_high_uncertainty_without_ood(
    signal_settings,
) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=["stale_news_context", "liquidity_context_fallback"]),
        settings=signal_settings,
        signal_row={
            "market_regime": "shock",
            "regime_confidence_0_1": 0.44,
            "probability_0_1": 0.82,
        },
        take_trade_prediction={
            "take_trade_prob": 0.51,
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.02,
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection={
            "expected_return_bps": 3.0,
            "expected_mae_bps": 35.0,
            "expected_mfe_bps": 20.0,
            "target_projection_diagnostics": {
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
                "max_bound_proximity_0_1": 0.72,
            },
        },
    )
    assert assessment["trade_action"] == "do_not_trade"
    assert "uncertainty_above_threshold" in assessment["abstention_reasons_json"]
    assert assessment["model_uncertainty_0_1"] > signal_settings.model_max_uncertainty


def test_uncertainty_hard_abstain_stale_feature_timestamp(signal_settings) -> None:
    old_ts = 1_700_000_000_000 - 400_000
    assessment = assess_model_uncertainty(
        ctx=_ctx(
            data_issues=[],
            primary_feature={
                "computed_ts_ms": old_ts,
                "spread_bps": 1.0,
                "execution_cost_bps": 2.0,
                "depth_to_bar_volume_ratio": 0.5,
                "liquidity_source": "orderbook_levels",
                "data_completeness_0_1": 0.95,
                "staleness_score_0_1": 0.1,
            },
        ),
        settings=signal_settings,
        signal_row={
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_confidence_0_1": 0.85,
            "probability_0_1": 0.7,
            "analysis_ts_ms": 1_700_000_000_000,
        },
        take_trade_prediction={
            "take_trade_prob": 0.72,
            "take_trade_calibration_method": "isotonic",
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.75,
                "ood_score_0_1": 0.05,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection={
            "expected_return_bps": 12.0,
            "expected_mae_bps": 20.0,
            "expected_mfe_bps": 30.0,
            "target_projection_diagnostics": {"max_bound_proximity_0_1": 0.1},
        },
    )
    assert assessment["trade_action"] == "do_not_trade"
    assert "feature_stale_hard_abstain" in assessment["abstention_reasons_json"]
    assert assessment["uncertainty_components"]["feature_age_ms"] == 400_000


def test_uncertainty_monitoring_hook_false_confidence(signal_settings) -> None:
    assessment = assess_model_uncertainty(
        ctx=_ctx(data_issues=[]),
        settings=signal_settings,
        signal_row={
            "market_regime": "trend",
            "regime_confidence_0_1": 0.9,
            "probability_0_1": 0.85,
        },
        take_trade_prediction={
            "take_trade_prob": 0.35,
            "take_trade_calibration_method": "isotonic",
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.88,
                "ood_score_0_1": 0.0,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection={
            "expected_return_bps": 10.0,
            "expected_mae_bps": 15.0,
            "expected_mfe_bps": 25.0,
            "target_projection_diagnostics": {"max_bound_proximity_0_1": 0.08},
        },
    )
    assert assessment["uncertainty_assessment"]["monitoring_hooks"]["false_confidence_risk"] is True


def test_uncertainty_execution_shadow_lane_from_spread(signal_settings) -> None:
    """Hohe Execution-Unsicherheit -> shadow_only auch ohne OOD-Alert."""
    assessment = assess_model_uncertainty(
        ctx=_ctx(
            data_issues=[],
            primary_feature={
                "computed_ts_ms": 1_700_000_000_000,
                "spread_bps": 7.4,
                "execution_cost_bps": 14.0,
                "depth_to_bar_volume_ratio": 0.35,
                "liquidity_source": "orderbook_levels",
                "data_completeness_0_1": 0.96,
            },
        ),
        settings=signal_settings.model_copy(
            update={
                "model_max_uncertainty": 0.99,
                "model_ood_hard_abstain_score": 0.99,
                "model_shadow_divergence_hard_abstain": 0.99,
                # Nur Execution/Daten duerfen shadow_only triggern, nicht der Aggregat-Score.
                "model_uncertainty_shadow_lane": 0.99,
                "model_ood_shadow_lane_score": 0.99,
                "model_shadow_divergence_shadow_lane": 0.99,
            }
        ),
        signal_row={
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_confidence_0_1": 0.88,
            "probability_0_1": 0.68,
            "analysis_ts_ms": 1_700_000_000_000,
        },
        take_trade_prediction={
            "take_trade_prob": 0.66,
            "take_trade_calibration_method": "isotonic",
            "take_trade_model_diagnostics": {
                "confidence_0_1": 0.72,
                "ood_score_0_1": 0.1,
                "ood_alert": False,
                "ood_reasons_json": [],
            },
        },
        target_projection={
            "expected_return_bps": 10.0,
            "expected_mae_bps": 18.0,
            "expected_mfe_bps": 28.0,
            "target_projection_diagnostics": {"max_bound_proximity_0_1": 0.1},
        },
    )
    assert assessment["trade_action"] == "allow_trade"
    assert assessment["uncertainty_gate_phase"] == "shadow_only"
    assert assessment["uncertainty_components"]["execution_uncertainty_0_1"] >= 0.52
    assert "execution_uncertainty_shadow_lane" in (
        assessment.get("uncertainty_lane_reasons_json") or []
    )


def _ctx(*, data_issues: list[str], primary_feature: dict | None = None) -> ScoringContext:
    pf = primary_feature or {"computed_ts_ms": 1_700_000_000_000}
    return ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature=pf,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
        data_issues=data_issues,
    )
