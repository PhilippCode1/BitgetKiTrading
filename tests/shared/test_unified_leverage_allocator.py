from __future__ import annotations

from types import SimpleNamespace

from shared_py.unified_leverage_allocator import (
    UNIFIED_LEVERAGE_ALLOCATOR_VERSION,
    extract_execution_leverage_cap_from_signal_row,
    recompute_unified_leverage_allocation,
    refresh_unified_leverage_allocation_in_snapshot,
)


def _settings(**kwargs: object) -> SimpleNamespace:
    base = dict(
        risk_allowed_leverage_min=7,
        risk_allowed_leverage_max=75,
        leverage_auto_execution_fraction_of_recommended_0_1=0.88,
        leverage_auto_execution_subtract_steps=0,
        leverage_family_max_cap_spot=5,
        leverage_family_max_cap_margin=25,
        leverage_family_max_cap_futures=75,
        leverage_cold_start_max_cap=12,
        leverage_cold_start_prior_signals_threshold=20,
        leverage_shadow_divergence_soft_cap_threshold_0_1=0.38,
        leverage_shadow_divergence_soft_max_leverage=14,
        leverage_stop_distance_scale_bps=180.0,
        leverage_tight_stop_exposure_threshold_pct=0.004,
        leverage_tight_stop_exposure_shrink_factor_0_1=0.60,
        leverage_account_heat_margin_soft_threshold_0_1=0.50,
        leverage_account_heat_execution_shrink_0_1=0.75,
        risk_leverage_cap_daily_drawdown_threshold_0_1=0.025,
        risk_leverage_cap_weekly_drawdown_threshold_0_1=0.06,
        risk_leverage_max_under_drawdown=10,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_recompute_execution_cap_below_recommended() -> None:
    st = _settings()
    out = recompute_unified_leverage_allocation(
        allowed_leverage=40,
        recommended_leverage=25,
        stop_distance_pct=0.01,
        meta_trade_lane="candidate_for_live",
        trade_action="allow_trade",
        governor={"max_exposure_fraction_0_1": 1.0},
        risk_account_snapshot={},
        signal_row={"market_family": "futures", "source_snapshot_json": {}},
        settings=st,
    )
    assert out["version"] == UNIFIED_LEVERAGE_ALLOCATOR_VERSION
    assert out["mirror_leverage"] == 25
    assert out["execution_leverage_cap"] is not None
    assert out["execution_leverage_cap"] <= 25


def test_cold_start_caps_execution() -> None:
    st = _settings()
    out = recompute_unified_leverage_allocation(
        allowed_leverage=40,
        recommended_leverage=25,
        stop_distance_pct=0.012,
        meta_trade_lane="candidate_for_live",
        trade_action="allow_trade",
        governor={"max_exposure_fraction_0_1": 1.0},
        risk_account_snapshot={},
        signal_row={
            "market_family": "futures",
            "source_snapshot_json": {"instrument_evidence_json": {"prior_signal_count": 3}},
        },
        settings=st,
    )
    assert out["instrument_evidence_tier"] == "cold_start"
    assert out["execution_leverage_cap"] is not None
    assert out["execution_leverage_cap"] <= 12


def test_extract_execution_cap_from_row() -> None:
    row = {
        "source_snapshot_json": {
            "hybrid_decision": {
                "leverage_allocator": {
                    "unified_leverage_allocation": {"execution_leverage_cap": 11}
                }
            }
        }
    }
    assert extract_execution_leverage_cap_from_signal_row(row) == 11


def test_evidence_cap_breakdown_includes_drawdown_binding() -> None:
    st = _settings(
        risk_leverage_cap_daily_drawdown_threshold_0_1=0.01,
        risk_leverage_max_under_drawdown=9,
    )
    out = recompute_unified_leverage_allocation(
        allowed_leverage=40,
        recommended_leverage=25,
        stop_distance_pct=0.012,
        meta_trade_lane="paper_only",
        trade_action="allow_trade",
        governor={"max_exposure_fraction_0_1": 1.0, "max_leverage_cap": 40},
        risk_account_snapshot={"daily_drawdown_0_1": 0.05},
        signal_row={"market_family": "futures", "source_snapshot_json": {}},
        settings=st,
    )
    assert "drawdown_kill_switch_cap" in out["binding_caps_json"]
    names = {x.get("name") for x in (out.get("evidence_cap_breakdown_json") or [])}
    assert "drawdown_kill_switch_cap" in names
    assert "risk_governor_model_quality_cap" in names


def test_refresh_writes_snapshot() -> None:
    db_row: dict = {
        "allowed_leverage": 30,
        "recommended_leverage": 22,
        "trade_action": "allow_trade",
        "meta_trade_lane": "candidate_for_live",
        "stop_distance_pct": 0.009,
        "source_snapshot_json": {
            "hybrid_decision": {
                "risk_governor": {"max_exposure_fraction_0_1": 0.65},
                "leverage_allocator": {"factor_caps": {"edge_factor_cap": 22}},
            },
            "stop_budget_assessment": {"stop_distance_pct": 0.009},
        },
    }
    st = _settings()
    u = refresh_unified_leverage_allocation_in_snapshot(db_row=db_row, settings=st)
    assert u is not None
    hd = db_row["source_snapshot_json"]["hybrid_decision"]
    assert "unified_leverage_allocation" in hd["leverage_allocator"]
