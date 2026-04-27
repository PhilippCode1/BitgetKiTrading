from __future__ import annotations

from shared_py.unified_exit_plan import (
    UNIFIED_EXIT_PLAN_VERSION,
    build_unified_exit_plan,
)


def test_unified_exit_plan_mfe_ladder_not_fixed_rr() -> None:
    row = {
        "direction": "long",
        "expected_mfe_bps": 100.0,
        "expected_mae_bps": 40.0,
    }
    edb = {"exit_family_effective_primary": "adaptive_scale_runner"}
    sba = {"outcome": "passed", "stop_distance_pct": 0.004}
    pf = {"atrp_14": 0.02, "spread_bps": 2.0}
    plan = build_unified_exit_plan(
        signal_row=row,
        end_decision_binding=edb,
        stop_budget_assessment=sba,
        primary_feature=pf,
    )
    assert plan["version"] == UNIFIED_EXIT_PLAN_VERSION
    assert len(plan["partial_take_profits"]) == 3
    assert plan["partial_take_profits"][0]["profit_capture_bps_from_entry"] == 35.0
    assert plan["mfe_mae_tp_family"]["tp_leg_model"] == "mfe_fraction_ladder"
    assert plan["trailing"]["mode"] != ""
    assert plan["structure_invalidation"]["mae_bps_threshold"] == 40.0


def test_unified_exit_plan_same_schema_minimal() -> None:
    plan = build_unified_exit_plan(
        signal_row={"direction": "short"},
        end_decision_binding=None,
        stop_budget_assessment={},
        primary_feature=None,
    )
    assert "initial_stop" in plan
    assert "time_stop" in plan
    assert "volatility_aware_profit_capture" in plan
