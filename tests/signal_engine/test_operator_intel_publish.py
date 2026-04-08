from __future__ import annotations

from signal_engine.operator_intel_publish import build_signal_operator_intel_payload


def test_build_signal_operator_intel_no_trade() -> None:
    bundle = {
        "event_payload": {
            "signal_id": "s1",
            "symbol": "BTCUSDT",
            "trade_action": "do_not_trade",
            "decision_state": "abstain",
            "risk_score_0_100": 40,
            "market_family": "futures",
        },
        "db_row": {
            "trade_action": "do_not_trade",
            "decision_state": "abstain",
            "reasons_json": {
                "specialists": {
                    "router_arbitration": {
                        "router_id": "deterministic_specialist_router_v1",
                        "selected_trade_action": "do_not_trade",
                        "router_reasons": ["uncertainty_high"],
                    },
                },
                "decision_control_flow": {
                    "no_trade_path": {"phase_block_drivers": ["stop_budget_blocked"]}
                },
            },
        },
    }
    pl = build_signal_operator_intel_payload(bundle)
    assert pl is not None
    assert pl["intel_kind"] == "no_trade"
    assert pl["correlation_id"] == "sig:s1"
    assert pl["symbol"] == "BTCUSDT"
    assert "uncertainty_high" in (pl.get("reasons") or [])
    assert "stop_budget_blocked" in (pl.get("reasons") or [])
    assert pl.get("specialist_route") == "deterministic_specialist_router_v1 / do_not_trade"


def test_build_signal_operator_intel_allow_trade_includes_context() -> None:
    bundle = {
        "event_payload": {
            "signal_id": "s2",
            "symbol": "ETHUSDT",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "risk_score_0_100": 78,
            "market_family": "margin",
            "market_regime": "trend",
            "playbook_id": "pb_breakout",
            "playbook_family": "breakout",
            "allowed_leverage": 12,
            "recommended_leverage": 9,
            "stop_fragility_0_1": 0.22,
            "stop_executability_0_1": 0.88,
            "signal_class": "gross",
        },
        "db_row": {
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "playbook_id": "pb_breakout",
            "playbook_family": "breakout",
            "market_regime": "trend",
            "reasons_json": {
                "specialists": {
                    "router_arbitration": {
                        "router_id": "deterministic_specialist_router_v1",
                        "selected_trade_action": "allow_trade",
                        "router_reasons": ["breakout_alignment"],
                    }
                }
            },
        },
    }
    pl = build_signal_operator_intel_payload(bundle)
    assert pl is not None
    assert pl["intel_kind"] == "strategy_intent"
    assert pl["severity"] == "warn"
    assert pl["specialist_route"] == "deterministic_specialist_router_v1 / allow_trade"
    assert pl["playbook_id"] == "pb_breakout"
    assert pl["market_family"] == "margin"
    assert "stop_fragility=0.22" in str(pl.get("risk_summary"))
    assert "breakout_alignment" in (pl.get("reasons") or [])
