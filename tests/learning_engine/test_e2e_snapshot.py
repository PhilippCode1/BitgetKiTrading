from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "services" / "learning-engine" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from learning_engine.e2e.qc import derive_trade_close_qc_labels
from learning_engine.e2e.snapshot import build_e2e_snapshot_from_signal_row, initial_outcomes_json


def test_build_snapshot_extracts_specialists_and_stop_budget() -> None:
    row = {
        "signal_id": "550e8400-e29b-41d4-a716-446655440000",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "analysis_ts_ms": 1_700_000_000_000,
        "market_family": "futures",
        "trade_action": "allow_trade",
        "playbook_id": "pb-trend-1",
        "playbook_family": "trend_continuation",
        "market_regime": "trend",
        "meta_trade_lane": "shadow",
        "scoring_model_version": "v1",
        "reasons_json": {
            "specialists": {
                "router_arbitration": {"selected_trade_action": "allow_trade"},
                "playbook_specialist": {
                    "proposal": {
                        "exit_family_primary": "scale_out",
                        "exit_families_ranked": ["scale_out", "runner"],
                        "stop_budget_0_1": 0.4,
                    }
                },
            }
        },
        "source_snapshot_json": {
            "stop_budget_assessment": {
                "policy_version": "stop-budget-v2",
                "outcome": "ok",
                "stop_fragility_0_1": 0.2,
            },
            "hybrid_decision": {
                "risk_governor": {
                    "hard_block_reasons_json": [],
                    "live_execution_block_reasons_json": ["ctx"],
                }
            },
        },
    }
    snap = build_e2e_snapshot_from_signal_row(row)
    assert snap["snapshot_schema_version"] == "e2e-snapshot-v1"
    assert snap["proposal_and_votes"]["router_arbitration"]["selected_trade_action"] == "allow_trade"
    assert snap["stop_and_execution_quality"]["stop_budget_assessment"]["policy_version"] == "stop-budget-v2"
    assert snap["final_decision"]["trade_action"] == "allow_trade"
    out0 = initial_outcomes_json(row)
    assert out0["shadow"] is not None
    assert out0["counterfactual"] is not None


def test_initial_outcomes_no_trade() -> None:
    row = {"trade_action": "do_not_trade", "meta_trade_lane": "live"}
    out = initial_outcomes_json(row)
    assert out["counterfactual"]["kind"] == "no_trade_at_decision"


def test_derive_qc_stop_tight() -> None:
    from decimal import Decimal

    qc = derive_trade_close_qc_labels(
        err_labels=["STOP_TOO_TIGHT", "STALE_DATA"],
        direction_correct=False,
        stop_hit=True,
        tp1_hit=False,
        take_trade_prob=0.7,
        pnl_net=Decimal("-1"),
    )
    assert qc["stop_too_tight"]["value"] is True
    assert "false_positive_trade_hypothesis" in qc
