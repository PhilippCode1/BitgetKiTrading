from __future__ import annotations

import pytest

from signal_engine.stop_budget_policy import (
    STOP_BUDGET_POLICY_VERSION,
    assess_stop_budget_policy,
    max_stop_budget_pct_for_leverage,
)


def test_max_stop_budget_at_anchor_and_floor(signal_settings) -> None:
    assert abs(max_stop_budget_pct_for_leverage(7, signal_settings) - 0.01) < 1e-9
    assert abs(max_stop_budget_pct_for_leverage(50, signal_settings) - 0.001) < 1e-9
    b30 = max_stop_budget_pct_for_leverage(30, signal_settings)
    assert 0.001 < b30 < 0.01


def test_assess_leverage_reduced_when_stop_wide_for_high_leverage(
    signal_settings,
) -> None:
    """Breiterer Stop als Budget bei hohem L -> Hebel runter bis Budget passt."""
    close = 100_000.0
    drawings = [
        {
            "type": "stop_zone",
            "geometry": {"price_low": "99380", "price_high": "99420"},
        },
    ]
    # mid 99400 -> distance 0.006
    row = {
        "direction": "long",
        "trade_action": "allow_trade",
        "market_regime": "trend",
        "allowed_leverage": 30,
        "recommended_leverage": 30,
        "expected_mae_bps": 12.0,
        "source_snapshot_json": {
            "instrument": {"market_family": "futures"},
            "hybrid_decision": {
                "leverage_allocator": {
                    "market_inputs": {"liquidation_proximity_stress_0_1": 0.2},
                },
            },
        },
    }
    pf = {
        "spread_bps": 1.0,
        "execution_cost_bps": 2.0,
        "volatility_cost_bps": 0.5,
        "atrp_14": 0.02,
        "impact_buy_bps_10000": 1.0,
    }
    a = assess_stop_budget_policy(
        settings=signal_settings,
        signal_row=row,
        drawings=drawings,
        last_close=close,
        primary_feature=pf,
        instrument_execution={"price_tick_size": "1"},
        stop_trigger_type="mark_price",
    )
    assert a["policy_version"] == STOP_BUDGET_POLICY_VERSION
    assert a["outcome"] == "leverage_reduced"
    assert a["leverage_after"] is not None
    assert int(a["leverage_after"]) < 30
    assert a["stop_to_spread_ratio"] is not None


def test_wrong_side_stop_blocked(signal_settings) -> None:
    close = 100_000.0
    drawings = [
        {
            "type": "stop_zone",
            "geometry": {"price_low": "100200", "price_high": "100300"},
        },
    ]
    row = {
        "direction": "long",
        "trade_action": "allow_trade",
        "market_regime": "trend",
        "allowed_leverage": 10,
        "expected_mae_bps": 10.0,
        "source_snapshot_json": {"instrument": {"market_family": "spot"}},
    }
    a = assess_stop_budget_policy(
        settings=signal_settings,
        signal_row=row,
        drawings=drawings,
        last_close=close,
        primary_feature={"spread_bps": 2.0},
        instrument_execution={"price_tick_size": "0.1"},
        stop_trigger_type="mark_price",
    )
    assert a["outcome"] == "blocked"
    assert any("protective" in str(x) for x in (a.get("gate_reasons_json") or []))


def test_global_cap_blocks_wider_than_one_percent(signal_settings) -> None:
    close = 100_000.0
    drawings = [
        {
            "type": "stop_zone",
            "geometry": {"price_low": "97000", "price_high": "97100"},
        },
    ]
    row = {
        "direction": "long",
        "trade_action": "allow_trade",
        "market_regime": "trend",
        "allowed_leverage": 7,
        "expected_mae_bps": 15.0,
        "source_snapshot_json": {"instrument": {"market_family": "spot"}},
    }
    a = assess_stop_budget_policy(
        settings=signal_settings,
        signal_row=row,
        drawings=drawings,
        last_close=close,
        primary_feature={"spread_bps": 1.0, "atrp_14": 0.01},
        instrument_execution={"price_tick_size": "1"},
        stop_trigger_type="mark_price",
    )
    assert a["outcome"] == "blocked"
    assert any("global_max" in str(x) for x in (a.get("gate_reasons_json") or []))


def test_blocked_budget_includes_exit_alternatives_and_ladder(
    signal_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unhaltbarer Stop vs. Budget bei min Hebel: Leiter + Exit-Familien-Kandidaten."""
    monkeypatch.setattr(signal_settings, "risk_allowed_leverage_min", 50, raising=False)
    close = 100_000.0
    drawings = [
        {
            "type": "stop_zone",
            "geometry": {"price_low": "99200", "price_high": "99250"},
        },
    ]
    row = {
        "direction": "long",
        "trade_action": "allow_trade",
        "market_regime": "trend",
        "allowed_leverage": 50,
        "expected_mae_bps": 5.0,
        "source_snapshot_json": {
            "instrument": {"market_family": "futures"},
            "hybrid_decision": {
                "leverage_allocator": {
                    "market_inputs": {"liquidation_proximity_stress_0_1": 0.1},
                },
            },
        },
        "reasons_json": {
            "specialists": {
                "playbook_specialist": {
                    "proposal": {
                        "exit_family_primary": "runner_wide",
                        "stop_budget_0_1": 0.72,
                    }
                },
            }
        },
    }
    pf = {
        "spread_bps": 0.5,
        "execution_cost_bps": 1.0,
        "volatility_cost_bps": 0.5,
        "atrp_14": 0.001,
        "impact_buy_bps_10000": 0.5,
    }
    a = assess_stop_budget_policy(
        settings=signal_settings,
        signal_row=row,
        drawings=drawings,
        last_close=close,
        primary_feature=pf,
        instrument_execution={"price_tick_size": "1"},
        stop_trigger_type="last",
    )
    assert a["outcome"] == "blocked"
    assert a["policy_version"] == STOP_BUDGET_POLICY_VERSION
    assert isinstance(a.get("resolution_ladder_json"), list)
    assert len(a["resolution_ladder_json"]) >= 2
    assert any("unsatisfiable" in str(x) for x in (a.get("gate_reasons_json") or []))
    alts = a.get("exit_family_alternatives_json") or []
    assert isinstance(alts, list)
    assert any(x.get("exit_family_primary") == "runner_wide" for x in alts)


def test_skipped_when_not_allow_trade(signal_settings) -> None:
    row = {
        "direction": "long",
        "trade_action": "do_not_trade",
        "source_snapshot_json": {},
    }
    a = assess_stop_budget_policy(
        settings=signal_settings,
        signal_row=row,
        drawings=[
            {"type": "stop_zone", "geometry": {"price_low": "9", "price_high": "10"}}
        ],
        last_close=100.0,
        primary_feature={},
        instrument_execution=None,
        stop_trigger_type="mark_price",
    )
    assert a["outcome"] == "skipped"
