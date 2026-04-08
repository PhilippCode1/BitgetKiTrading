from __future__ import annotations

import ast
from pathlib import Path

from signal_engine.decision_control_flow import (
    PHASE_ORDER,
    build_decision_control_flow,
)


def _base_row() -> dict:
    return {
        "trade_action": "allow_trade",
        "meta_trade_lane": "live",
        "decision_state": "accepted",
        "signal_class": "kern",
        "take_trade_prob": 0.6,
        "expected_return_bps": 10.0,
        "expected_mae_bps": 5.0,
        "expected_mfe_bps": 20.0,
        "market_regime": "trend",
        "regime_bias": "neutral",
        "regime_confidence_0_1": 0.7,
        "probability_0_1": 0.55,
        "signal_strength_0_100": 60,
        "model_uncertainty_0_1": 0.2,
        "model_ood_score_0_1": 0.1,
        "model_ood_alert": False,
        "uncertainty_execution_lane": "full",
        "uncertainty_gate_phase": "full",
        "decision_policy_version": "test",
        "allowed_leverage": 3.0,
        "recommended_leverage": 2.0,
        "decision_confidence_0_1": 0.65,
        "rejection_reasons_json": [],
        "meta_decision_action": "allow_trade_candidate",
        "meta_decision_kernel_version": "mdk-v1",
        "meta_decision_bundle_json": {"expected_utility_proxy_0_1": 0.5},
        "reasons_json": {
            "deterministic_gates": {
                "rejection_state": False,
                "decision_state": "accepted",
                "rejection_reasons_json": [],
            },
            "online_drift": {
                "enable_online_drift_block": False,
                "effective_action": "noop",
            },
            "meta_decision_kernel": {
                "kernel_forces_do_not_trade": False,
                "abstention_codes": [],
            },
        },
        "source_snapshot_json": {
            "quality_gate": {"passed": True},
            "uncertainty_gate": {},
            "hybrid_decision": {"trade_action": "allow_trade"},
            "stop_budget_assessment": {"outcome": "skipped", "policy_version": "stop-budget-v2"},
        },
    }


def test_hybrid_phase_includes_structured_market_context_in_evidence() -> None:
    row = _base_row()
    smc = {"version": "smc-v1", "surprise_score_0_1": 0.41}
    row["source_snapshot_json"]["structured_market_context"] = smc
    dcf = build_decision_control_flow(row)
    hybrid = next(p for p in dcf["phases"] if p["id"] == "hybrid_risk_leverage_meta")
    assert hybrid["evidence"]["structured_market_context"] == smc


def test_phase_order_matches_built_phases() -> None:
    row = _base_row()
    dcf = build_decision_control_flow(row)
    ids = [p["id"] for p in dcf["phases"]]
    expected = [pid for pid, _ in PHASE_ORDER]
    assert ids == expected
    assert dcf["pipeline_version"] == "se-end-decision-v4"
    assert "end_decision_binding" in dcf
    assert "no_trade_path" in dcf


def test_data_quality_failed_when_quality_gate_false() -> None:
    row = _base_row()
    row["source_snapshot_json"]["quality_gate"]["passed"] = False
    dcf = build_decision_control_flow(row)
    dq = next(p for p in dcf["phases"] if p["id"] == "data_quality")
    assert dq["outcome"] == "failed"


def test_deterministic_safety_blocked_when_rejection_state() -> None:
    row = _base_row()
    row["reasons_json"]["deterministic_gates"]["rejection_state"] = True
    row["reasons_json"]["deterministic_gates"]["rejection_reasons_json"] = ["hard_rule"]
    dcf = build_decision_control_flow(row)
    det = next(p for p in dcf["phases"] if p["id"] == "deterministic_safety")
    assert det["outcome"] == "blocked"


def test_probabilistic_models_degraded_when_take_prob_missing() -> None:
    row = _base_row()
    row["take_trade_prob"] = None
    dcf = build_decision_control_flow(row)
    prob = next(p for p in dcf["phases"] if p["id"] == "probabilistic_models")
    assert prob["outcome"] == "degraded"


def test_online_drift_blocked_when_rejection_lists_hard_block() -> None:
    row = _base_row()
    row["rejection_reasons_json"] = ["online_drift_hard_block", "other"]
    dcf = build_decision_control_flow(row)
    od = next(p for p in dcf["phases"] if p["id"] == "online_drift_optional")
    assert od["outcome"] == "blocked"


def test_specialist_arbitration_phase_present() -> None:
    row = _base_row()
    dcf = build_decision_control_flow(row)
    sp = next(p for p in dcf["phases"] if p["id"] == "specialist_arbitration")
    assert sp["order"] == 8
    assert sp["outcome"] == "skipped"


def test_end_decision_binding_from_specialist_proposals() -> None:
    row = _base_row()
    row["playbook_id"] = "trend_continuation_core"
    row["playbook_family"] = "trend_continuation"
    row["reasons_json"]["specialists"] = {
        "base_model": {
            "proposal": {
                "stop_budget_0_1": 0.55,
                "exit_family_primary": "adaptive_scale_runner",
                "exit_families_ranked": ["time_stop"],
                "leverage_band": {"min_fraction_0_1": 0.3, "max_fraction_0_1": 1.0},
            }
        },
        "playbook_specialist": {
            "proposal": {
                "stop_budget_0_1": 0.4,
                "exit_family_primary": "scale_out",
                "exit_families_ranked": ["runner", "scale_out"],
                "leverage_band": {"min_fraction_0_1": 0.4, "max_fraction_0_1": 0.95},
            }
        },
        "router_arbitration": {
            "pre_adversary_trade_action": "allow_trade",
            "selected_trade_action": "allow_trade",
        },
        "ensemble_contract": {"ensemble_router_version": "ensemble-router-v2"},
    }
    dcf = build_decision_control_flow(row)
    edb = dcf["end_decision_binding"]
    assert edb["stop_budget_0_1"] == 0.4
    assert edb["exit_family_primary"] == "scale_out"
    assert edb["leverage_band_fraction_0_1"]["min"] == 0.4
    assert edb["leverage_band_fraction_0_1"]["max"] == 0.95
    assert dcf.get("exit_family_resolution") is not None
    assert edb.get("exit_family_effective_primary")
    assert isinstance(edb.get("exit_families_effective_ranked"), list)
    assert edb.get("exit_family_resolution_version")


def test_no_trade_path_lists_hybrid_when_hybrid_blocked() -> None:
    row = _base_row()
    row["trade_action"] = "do_not_trade"
    row["source_snapshot_json"]["hybrid_decision"] = {"trade_action": "do_not_trade"}
    dcf = build_decision_control_flow(row)
    ntp = dcf["no_trade_path"]
    assert ntp["no_trade_is_final_outcome"] is True
    drivers = [d.get("phase_id") for d in ntp.get("phase_block_drivers") or []]
    assert "hybrid_risk_leverage_meta" in drivers


def test_signal_engine_package_has_no_llm_vendor_imports() -> None:
    """Kern-Signal-Engine importiert keine LLM-Vendor-Pakete (Entkopplung)."""
    root = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "signal-engine"
        / "src"
        / "signal_engine"
    )
    banned_roots = frozenset(
        {"openai", "anthropic", "langchain", "langchain_core", "litellm", "tiktoken"}
    )
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = (alias.name or "").split(".", 1)[0]
                    if top in banned_roots:
                        offenders.append(f"{path.name}:{top}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".", 1)[0]
                if top in banned_roots:
                    offenders.append(f"{path.name}:from {top}")
    assert not offenders, "LLM-Vendor-Importe in signal_engine: " + ", ".join(offenders)
