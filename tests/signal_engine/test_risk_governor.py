from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (
    ROOT / "services" / "signal-engine" / "src",
    ROOT / "shared" / "python" / "src",
):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.config import SignalEngineSettings
from signal_engine.hybrid_decision import assess_hybrid_decision
from signal_engine.risk_governor import (
    RISK_GOVERNOR_VERSION,
    apply_live_ramp_cap,
    assess_risk_governor,
    leverage_escalation_ok,
)


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch) -> SignalEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    return SignalEngineSettings()


def _row(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
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
        "model_ood_score_0_1": 0.12,
        "model_ood_alert": False,
        "uncertainty_gate_phase": "full",
        "trade_action": "allow_trade",
        "decision_state": "accepted",
        "rejection_state": False,
        "signal_class": "kern",
        "risk_score_0_100": 62.0,
        "abstention_reasons_json": [],
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
    base.update(kwargs)
    return base


def test_margin_stress_moves_to_live_execution_not_hybrid_block(
    signal_settings: SignalEngineSettings,
) -> None:
    """Default RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY: Margin blockt nur Live, nicht Hybrid/Paper."""
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"margin_utilization_0_1": 0.99},
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_margin_utilization_exceeded" in gov["live_execution_block_reasons_json"]
    assert "risk_governor_margin_utilization_exceeded" not in gov["hard_block_reasons_json"]
    assert gov["hard_block_reasons_json"] == []
    out = assess_hybrid_decision(settings=signal_settings, signal_row=row)
    assert out["trade_action"] == "allow_trade"
    assert "risk_governor_margin_utilization_exceeded" not in out["abstention_reasons_json"]
    assert "risk_governor_margin_utilization_exceeded" in out["live_execution_block_reasons_json"]


def test_margin_utilization_at_config_limit_not_blocked(
    signal_settings: SignalEngineSettings,
) -> None:
    """Grenze ist strikt `>` (Float-Epsilon): exakt Limit = kein Hard-Block."""
    limit = float(signal_settings.risk_max_account_margin_usage)
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"margin_utilization_0_1": limit},
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_margin_utilization_exceeded" not in gov["live_execution_block_reasons_json"]


def test_largest_position_risk_breaches_live_block(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"largest_position_risk_to_equity_0_1": 0.99},
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_largest_position_risk_exceeded" in gov["live_execution_block_reasons_json"]


def test_margin_utilization_one_epsilon_above_limit_blocks(
    signal_settings: SignalEngineSettings,
) -> None:
    limit = float(signal_settings.risk_max_account_margin_usage)
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"margin_utilization_0_1": limit + 1e-9},
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_margin_utilization_exceeded" in gov["live_execution_block_reasons_json"]


def test_account_stress_merged_into_hard_when_legacy_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY", "false")
    st = SignalEngineSettings()
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"margin_utilization_0_1": 0.99},
        }
    )
    gov = assess_risk_governor(settings=st, signal_row=row, direction="long")
    assert "risk_governor_margin_utilization_exceeded" in gov["hard_block_reasons_json"]
    out = assess_hybrid_decision(settings=st, signal_row=row)
    assert out["trade_action"] == "do_not_trade"


def test_portfolio_venue_degraded_live_block(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {
                "portfolio_risk_json": {"venue_operational_mode": "degraded"},
            },
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "portfolio_live_venue_degraded" in gov["live_execution_block_reasons_json"]


def test_hard_block_exchange_health(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {"exchange_health_ok": False},
        }
    )
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_exchange_health_bad" in gov["hard_block_reasons_json"]
    assert "risk_governor_exchange_health_bad" in gov["universal_hard_block_reasons_json"]


def test_uncertainty_blocked_phase_hard_stop(signal_settings: SignalEngineSettings) -> None:
    row = _row(uncertainty_gate_phase="blocked")
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert "risk_governor_uncertainty_phase_blocked" in gov["hard_block_reasons_json"]


def test_high_uncertainty_lowers_leverage_cap(signal_settings: SignalEngineSettings) -> None:
    row = _row(model_uncertainty_0_1=0.70)
    gov = assess_risk_governor(settings=signal_settings, signal_row=row, direction="long")
    assert gov["max_leverage_cap"] <= 18
    assert gov["quality_tier"] in {"A", "B", "C", "D"}


def test_live_ramp_caps_candidate_lane(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        signal_class="gross",
        take_trade_prob=0.81,
        expected_return_bps=18.0,
        expected_mae_bps=20.0,
        expected_mfe_bps=34.0,
        model_uncertainty_0_1=0.14,
    )
    out = assess_hybrid_decision(settings=signal_settings, signal_row=row)
    assert out["meta_trade_lane"] == "candidate_for_live"
    assert out["trade_action"] == "allow_trade"
    assert out["allowed_leverage"] == signal_settings.risk_governor_live_ramp_max_leverage
    assert out["recommended_leverage"] == signal_settings.risk_governor_live_ramp_max_leverage


def test_live_ramp_lifted_with_escalation_flags(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        signal_class="gross",
        take_trade_prob=0.81,
        expected_return_bps=18.0,
        expected_mae_bps=20.0,
        expected_mfe_bps=34.0,
        model_uncertainty_0_1=0.14,
        source_snapshot_json={
            **_row()["source_snapshot_json"],  # type: ignore[arg-type]
            "risk_account_snapshot": {
                "leverage_escalation_approved": True,
                "measurably_stable_for_escalation": True,
            },
        },
    )
    out = assess_hybrid_decision(settings=signal_settings, signal_row=row)
    assert out["meta_trade_lane"] == "candidate_for_live"
    assert out["recommended_leverage"] is not None
    assert out["recommended_leverage"] > signal_settings.risk_governor_live_ramp_max_leverage


def test_paper_lane_not_live_ramped(signal_settings: SignalEngineSettings) -> None:
    row = _row(
        risk_score_0_100=40.0,
        take_trade_prob=0.74,
        expected_return_bps=16.0,
        expected_mae_bps=24.0,
        expected_mfe_bps=34.0,
        model_uncertainty_0_1=0.20,
    )
    out = assess_hybrid_decision(settings=signal_settings, signal_row=row)
    assert out["meta_trade_lane"] == "paper_only"
    assert out["recommended_leverage"] is not None
    assert out["recommended_leverage"] > 7


def test_apply_live_ramp_cap_unit() -> None:
    class _S:
        risk_governor_live_ramp_max_leverage = 7

    a, r = apply_live_ramp_cap(
        settings=_S(),
        meta_trade_lane="candidate_for_live",
        allowed_leverage=40,
        recommended_leverage=35,
        signal_row={"source_snapshot_json": {}},
        governor={"version": RISK_GOVERNOR_VERSION},
    )
    assert a == 7 and r == 7


def test_leverage_escalation_ok_requires_both_flags() -> None:
    row = {
        "source_snapshot_json": {
            "risk_account_snapshot": {"leverage_escalation_approved": True},
        }
    }
    assert not leverage_escalation_ok(row, {})
