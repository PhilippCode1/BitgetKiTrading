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

from signal_engine.meta_decision_kernel import apply_meta_decision_kernel


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()


def _base_row(**overrides):
    row = {
        "trade_action": "allow_trade",
        "meta_trade_lane": "paper_only",
        "decision_state": "accepted",
        "take_trade_prob": 0.65,
        "expected_return_bps": 20.0,
        "expected_mae_bps": 40.0,
        "expected_mfe_bps": 80.0,
        "take_trade_calibration_method": "platt",
        "model_uncertainty_0_1": 0.2,
        "model_ood_alert": False,
        "model_ood_score_0_1": 0.1,
        "shadow_divergence_0_1": 0.05,
        "stop_executability_0_1": 0.8,
        "uncertainty_gate_phase": "full",
        "source_snapshot_json": {
            "quality_gate": {"passed": True},
            "uncertainty_gate": {"gate_phase": "full"},
            "hybrid_decision": {
                "take_trade_prob_adjusted_0_1": 0.62,
                "risk_governor": {
                    "universal_hard_block_reasons_json": [],
                    "live_execution_block_reasons_json": [],
                },
            },
        },
        "reasons_json": {
            "specialists": {
                "router_arbitration": {"operator_gate_required": False},
                "adversary_check": {
                    "dissent_score_0_1": 0.1,
                    "hard_veto_recommended": False,
                },
            }
        },
        "abstention_reasons_json": [],
        "rejection_reasons_json": [],
    }
    row.update(overrides)
    return row


def test_meta_kernel_allow_trade_candidate(signal_settings) -> None:
    out = apply_meta_decision_kernel(settings=signal_settings, db_row=_base_row())
    assert out["meta_decision_action"] == "allow_trade_candidate"
    assert out["kernel_forces_do_not_trade"] is False
    assert out["meta_decision_bundle_json"]["expected_utility_proxy_0_1"] >= 0.0


def test_meta_kernel_do_not_trade_on_high_uncertainty(signal_settings) -> None:
    out = apply_meta_decision_kernel(
        settings=signal_settings,
        db_row=_base_row(model_uncertainty_0_1=0.99),
    )
    assert out["kernel_forces_do_not_trade"] is True
    assert out["meta_decision_action"] == "do_not_trade"


def test_meta_kernel_operator_release_pending(signal_settings) -> None:
    row = _base_row()
    hd = row["source_snapshot_json"]["hybrid_decision"]
    hd["risk_governor"]["live_execution_block_reasons_json"] = ["account_stress_demo"]
    out = apply_meta_decision_kernel(settings=signal_settings, db_row=row)
    assert out["kernel_forces_do_not_trade"] is False
    assert out["meta_decision_action"] == "operator_release_pending"


def test_meta_kernel_blocked_by_policy_layer(signal_settings) -> None:
    row = _base_row(
        trade_action="do_not_trade",
        abstention_reasons_json=["playbook_blacklist:demo"],
    )
    out = apply_meta_decision_kernel(settings=signal_settings, db_row=row)
    assert out["meta_decision_action"] == "blocked_by_policy"


def test_meta_kernel_candidate_for_live(signal_settings) -> None:
    out = apply_meta_decision_kernel(
        settings=signal_settings,
        db_row=_base_row(meta_trade_lane="candidate_for_live"),
    )
    assert out["meta_decision_action"] == "candidate_for_live"
