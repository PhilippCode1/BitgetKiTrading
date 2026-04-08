from __future__ import annotations

from decimal import Decimal

from shared_py.exit_engine import (
    build_live_exit_plans,
    evaluate_exit_plan,
    leverage_indexed_stop_budget_bps,
    merge_exit_build_overrides,
    merge_plan_override,
    parse_plan_json,
    run_unified_exit_evaluation,
    validate_exit_plan,
)


def test_evaluate_exit_plan_zero_qty_no_close_despite_stop_hit() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1.0"),
        break_even_after_tp_index=0,
        timeframe="5m",
    )
    decision = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("0"),
        mark_price=Decimal("90"),
        fill_price=Decimal("90"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )
    assert not any(a.get("action") == "close_full" for a in decision["actions"])
    assert not any(a.get("action") == "close_partial" for a in decision["actions"])


def test_validate_exit_plan_blocks_risk_and_leverage_conflicts() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("99.2"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=True,
        runner_trail_mult=Decimal("1.0"),
        break_even_after_tp_index=0,
        timeframe="5m",
    )

    validation = validate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        leverage=Decimal("15"),
        allowed_leverage=7,
        max_position_risk_pct=0.02,
        risk_trade_action="do_not_trade",
    )

    assert validation["valid"] is False
    assert "risk_engine_blocks_exit_plan" in validation["reasons"]
    assert "exit_plan_exceeds_allowed_leverage" in validation["reasons"]
    assert "exit_plan_position_risk_exceeds_max" in validation["reasons"]


def test_evaluate_exit_plan_applies_partials_break_even_and_trailing() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("97"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=True,
        runner_trail_mult=Decimal("1.0"),
        break_even_after_tp_index=0,
        timeframe="5m",
    )

    decision = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("105"),
        fill_price=Decimal("105"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )

    close_actions = [
        action for action in decision["actions"] if action["action"] == "close_partial"
    ]
    assert [action["tp_index"] for action in close_actions] == [0, 1]
    assert [action["qty"] for action in close_actions] == ["0.30000000", "0.30000000"]
    assert "break_even_applied" in decision["reasons"]
    assert "runner_armed" in decision["reasons"]
    assert decision["updated_tp_plan"]["execution_state"]["hit_tp_indices"] == [0, 1]
    assert decision["updated_tp_plan"]["break_even"]["applied"] is True
    assert decision["updated_tp_plan"]["runner"]["armed"] is True
    assert decision["updated_tp_plan"]["runner"]["trail_stop"] == "102.0"
    assert decision["updated_stop_plan"]["stop_price"] == "100"


def test_parse_plan_json_accepts_dict_and_string() -> None:
    d = {"a": 1}
    assert parse_plan_json(d) == d
    assert parse_plan_json('{"x": 2}') == {"x": 2}
    assert parse_plan_json(None) is None
    assert parse_plan_json("not-json") is None
    assert parse_plan_json("[1]") is None


def test_merge_plan_override_targets_runner_break_even() -> None:
    base_stop = {"stop_price": "99"}
    base_tp = {
        "targets": [{"take_pct": "0.5"}],
        "runner": {"mode": "a"},
        "break_even": {"enabled": True},
    }
    o_stop = {"stop_price": "98"}
    o_tp = {
        "targets": [{"take_pct": "0.3"}],
        "runner": {"trail_offset": "1"},
        "break_even": {"applied": False},
        "extra": None,
    }
    s, t = merge_plan_override(base_stop, base_tp, o_stop, o_tp)
    assert s["stop_price"] == "98"
    assert t["targets"] == [{"take_pct": "0.3"}]
    assert t["runner"]["mode"] == "a"
    assert t["runner"]["trail_offset"] == "1"
    assert t["break_even"]["applied"] is False


def test_build_live_exit_plans_optional_stop_or_tp() -> None:
    s_none, t_ok = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=None,
        take_profit=Decimal("110"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.3"), Decimal("0.3"), Decimal("0.4")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
    )
    assert s_none is None
    assert t_ok is not None

    s_ok, t_none = build_live_exit_plans(
        side="short",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("102"),
        take_profit=None,
        stop_trigger_type="fill_price",
        tp_trigger_type="mark_price",
        take_pcts=(Decimal("0.3"), Decimal("0.3"), Decimal("0.4")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
    )
    assert s_ok is not None
    assert t_none is None


def test_evaluate_exit_plan_stop_hit_short() -> None:
    stop_plan = {
        "trigger_type": "fill_price",
        "stop_price": "101",
        "execution": {
            "reduce_only": True,
            "order_type": "market",
            "timing": "immediate",
        },
    }
    tp_plan = {
        "trigger_type": "fill_price",
        "targets": [],
        "execution": {},
        "execution_state": {"hit_tp_indices": [], "initial_qty": "1"},
        "runner": {"armed": False},
        "break_even": {"enabled": False},
    }
    out = evaluate_exit_plan(
        side="short",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("100"),
        fill_price=Decimal("101"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )
    assert out["actions"][0]["action"] == "close_full"
    assert out["actions"][0]["reason_code"] == "stop_loss_hit"


def test_evaluate_exit_plan_runner_trail_hit() -> None:
    tp_plan = {
        "trigger_type": "fill_price",
        "targets": [],
        "execution": {},
        "execution_state": {"hit_tp_indices": [], "initial_qty": "1"},
        "runner": {
            "armed": True,
            "trail_stop": "104",
            "trigger_type": "fill_price",
        },
        "break_even": {"enabled": False},
    }
    out = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("103"),
        fill_price=Decimal("103"),
        stop_plan=None,
        tp_plan=tp_plan,
    )
    assert out["actions"][0]["reason_code"] == "runner_trail_hit"


def test_validate_exit_plan_price_relation_short() -> None:
    stop_plan = {"stop_price": "99", "execution": {}}
    tp_plan = {
        "targets": [{"target_price": "101", "take_pct": "1"}],
        "execution": {},
    }
    v = validate_exit_plan(
        side="short",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )
    assert "take_profit_not_below_entry" in v["reasons"]
    assert "stop_loss_not_above_entry" in v["reasons"]


def test_validate_exit_plan_take_pct_sum_and_invalid_target() -> None:
    stop_plan = {"stop_price": "99", "execution": {}}
    tp_plan = {
        "targets": [
            {"target_price": "0", "take_pct": "0.6"},
            {"target_price": "110", "take_pct": "0.6"},
        ],
        "execution": {},
    }
    v = validate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )
    assert "take_profit_price_invalid" in v["reasons"]
    assert "take_profit_pct_sum_exceeds_1" in v["reasons"]


def test_evaluate_exit_plan_time_stop_expired() -> None:
    deadline = 1_700_000_000_000
    stop_plan = {
        "trigger_type": "mark_price",
        "stop_price": "90",
        "time_stop": {"enabled": True, "deadline_ts_ms": deadline, "fired": False},
        "execution": {"reduce_only": True, "order_type": "market", "timing": "immediate"},
    }
    tp_plan = {
        "trigger_type": "fill_price",
        "targets": [],
        "execution": {},
        "execution_state": {"hit_tp_indices": [], "initial_qty": "1"},
        "runner": {"armed": False},
        "break_even": {"enabled": False},
    }
    out = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("100"),
        fill_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        now_ms=deadline + 60_000,
    )
    assert out["reasons"] == ["time_stop_expired"]
    assert out["actions"][0]["reason_code"] == "time_stop_expired"
    assert out["updated_stop_plan"]["time_stop"]["fired"] is True


def test_evaluate_exit_plan_emergency_flatten() -> None:
    stop_plan = {
        "trigger_type": "mark_price",
        "stop_price": "95",
        "force_emergency_close": True,
        "execution": {"reduce_only": True, "order_type": "market", "timing": "immediate"},
    }
    out = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("100"),
        fill_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=None,
    )
    assert out["reasons"] == ["emergency_flatten"]
    assert out["updated_stop_plan"]["force_emergency_close"] is False


def test_validate_exit_plan_liquidation_buffer_long() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("98.2"),
        take_profit=Decimal("110"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
    )
    v = validate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        leverage=Decimal("50"),
        min_liquidation_buffer_bps=Decimal("50"),
    )
    assert "stop_inside_liquidation_buffer" in v["reasons"]


def test_validate_exit_plan_gap_stop_too_tight() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("99.95"),
        take_profit=Decimal("110"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
    )
    v = validate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        mark_price=Decimal("100"),
        fill_price=Decimal("99.5"),
        gap_stop_max_ratio=0.2,
    )
    assert "exit_plan_gap_stop_too_tight_vs_spread" in v["reasons"]


def test_leverage_indexed_stop_budget_curve_tightens_with_higher_leverage() -> None:
    low = leverage_indexed_stop_budget_bps(Decimal("7"))
    high = leverage_indexed_stop_budget_bps(Decimal("75"))
    assert low == Decimal("100")
    assert high == Decimal("10")


def test_validate_exit_plan_flags_microstructure_infeasible_stop_budget() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("99.85"),
        take_profit=Decimal("101.5"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
    )
    v = validate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        leverage=Decimal("50"),
        market_family="futures",
        spread_bps=Decimal("12"),
        depth_ratio=0.30,
    )
    assert "leverage_budget_infeasible_for_market_microstructure" in v["reasons"]


def test_run_unified_exit_evaluation_alias_matches_evaluate() -> None:
    stop_plan, tp_plan = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("97"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.30"), Decimal("0.30"), Decimal("0.40")),
        runner_enabled=True,
        runner_trail_mult=Decimal("1.0"),
        break_even_after_tp_index=0,
    )
    kwargs = dict(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("105"),
        fill_price=Decimal("105"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
    )
    assert run_unified_exit_evaluation(**kwargs) == evaluate_exit_plan(**kwargs)


def test_merge_exit_build_overrides_flatten_fast_preserves_total_weight() -> None:
    base = (Decimal("0.3"), Decimal("0.3"), Decimal("0.4"))
    ov = merge_exit_build_overrides(
        take_pcts=base,
        runner_enabled=True,
        runner_trail_mult=Decimal("1.2"),
        break_even_after_tp_index=1,
        hints={
            "take_pct_profile": "flatten_fast",
            "runner_enabled": False,
            "break_even_after_tp_index": 0,
        },
    )
    assert ov["runner_enabled"] is False
    assert ov["break_even_after_tp_index"] == 0
    assert abs(sum(ov["take_pcts"]) - sum(base)) < Decimal("0.0000001")


def test_build_live_exit_plans_runner_arm_after_tp_index() -> None:
    _s, t = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("110"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.3"), Decimal("0.3"), Decimal("0.4")),
        runner_enabled=True,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
        runner_arm_after_tp_index=0,
    )
    assert t is not None
    assert t["runner"]["arm_after_tp_index"] == 0
    assert t["runner"]["arm_after_tp2"] is False


def test_build_live_exit_plans_unified_meta_and_time_stop() -> None:
    s, t = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("110"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(Decimal("0.3"), Decimal("0.3"), Decimal("0.4")),
        runner_enabled=False,
        runner_trail_mult=Decimal("1"),
        break_even_after_tp_index=0,
        time_stop_deadline_ts_ms=2_000_000_000_000,
    )
    assert s is not None
    assert s["unified_exit"]["pipeline_version"] == "shared-exit-v2"
    assert s["time_stop"]["deadline_ts_ms"] == 2_000_000_000_000
    assert t is not None
    assert t["unified_exit"]["pipeline_version"] == "shared-exit-v2"
