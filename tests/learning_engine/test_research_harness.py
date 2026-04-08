from __future__ import annotations

import json
import uuid

from learning_engine.research.harness import (
    build_benchmark_evidence_report,
    report_to_markdown,
)
from shared_py.replay_determinism import FLOAT_METRICS_RTOL


def _eval_row(
    *,
    decision_ts_ms: int,
    take_trade_label: bool,
    feature_snapshot: dict | None = None,
    contract_version: str | None = "v_test_a",
) -> dict:
    eid = uuid.uuid4()
    mc: dict = {}
    if contract_version:
        mc["feature_schema_version"] = contract_version
    return {
        "evaluation_id": str(eid),
        "decision_ts_ms": decision_ts_ms,
        "closed_ts_ms": decision_ts_ms + 60_000,
        "take_trade_label": take_trade_label,
        "feature_snapshot_json": feature_snapshot or {
            "primary": {
                "ret_5": 0.001,
                "momentum_score": 50.0,
                "rsi_14": 45.0,
                "spread_bps": 5.0,
                "execution_cost_bps": 10.0,
            }
        },
        "signal_snapshot_json": {"playbook_family": "trend_follow"},
        "error_labels_json": [],
        "pnl_net_usdt": "1.0",
        "expected_return_bps": 12.0,
        "model_contract_json": mc,
    }


def test_build_benchmark_evidence_report_sorts_and_shape() -> None:
    r1 = _eval_row(decision_ts_ms=3000, take_trade_label=True, contract_version="v1")
    r2 = _eval_row(decision_ts_ms=1000, take_trade_label=False, contract_version="v1")
    r3 = _eval_row(decision_ts_ms=2000, take_trade_label=True, contract_version="v2")
    # absichtlich unsortiert übergeben
    report = build_benchmark_evidence_report(
        evaluation_rows=[r1, r2, r3],
        e2e_rows=[],
        symbol_filter=None,
        limit_evaluations=100,
        limit_e2e=50,
        min_rows_model_contract_slice=1,
    )
    assert report["evaluation_row_count"] == 3
    assert report["report_schema_version"] == "research-benchmark-evidence-v1"
    det = report.get("determinism") or {}
    assert det.get("float_metrics_rtol") == FLOAT_METRICS_RTOL
    assert "non_deterministic_factors_de" in det
    assert "baselines_vs_take_trade_label" in report
    assert "always_no_trade" in report["baselines_vs_take_trade_label"]
    sys_m = report["system_vs_take_trade_label"]
    assert sys_m.get("n") == 3
    assert sys_m.get("agreement_rate_with_take_trade_label") == 1.0


def test_model_contract_slices_min_rows() -> None:
    rows = [_eval_row(decision_ts_ms=1000 + i, take_trade_label=i % 2 == 0, contract_version="vx") for i in range(25)]
    report = build_benchmark_evidence_report(
        evaluation_rows=rows,
        e2e_rows=None,
        symbol_filter=None,
        limit_evaluations=500,
        limit_e2e=50,
        min_rows_model_contract_slice=20,
    )
    slices = report.get("by_model_contract_feature_schema_version") or {}
    assert "vx" in slices
    assert slices["vx"]["n"] == 25


def test_report_to_markdown_contains_sections() -> None:
    report = build_benchmark_evidence_report(
        evaluation_rows=[_eval_row(decision_ts_ms=1, take_trade_label=True)],
        e2e_rows=[],
        symbol_filter=None,
        limit_evaluations=10,
        limit_e2e=5,
        min_rows_model_contract_slice=1,
    )
    md = report_to_markdown(report)
    assert "Research Benchmark Evidence" in md
    assert "Determinismus" in md


def test_counterfactual_lane_sample() -> None:
    snap = {
        "proposal_and_votes": {
            "specialists": {
                "playbook_specialist": {
                    "proposal": {"counterfactual_candidates": ["pb_alt_1", "pb_alt_2"]}
                }
            }
        },
        "leverage_band": {"recommended_leverage": 7.0, "execution_leverage_cap": 10.0},
        "final_decision": {"trade_action": "allow_trade"},
    }
    e2e = {
        "signal_id": str(uuid.uuid4()),
        "decision_ts_ms": 99,
        "snapshot_json": json.dumps(snap),
        "outcomes_json": json.dumps(
            {
                "paper": {"pnl_net_usdt": "1", "phase": "closed"},
                "shadow": {"pnl_net_usdt": "0.5", "phase": "closed"},
            }
        ),
    }
    report = build_benchmark_evidence_report(
        evaluation_rows=[_eval_row(decision_ts_ms=1, take_trade_label=True)],
        e2e_rows=[e2e],
        symbol_filter=None,
        limit_evaluations=10,
        limit_e2e=10,
    )
    cfs = report.get("counterfactual_specimens") or []
    assert cfs
    assert any("router_alternate_playbook_candidate" in json.dumps(c) for c in cfs)
    lanes = report.get("lane_comparison_closed_pnl") or {}
    assert lanes.get("rows_with_any_closed_pnl", 0) >= 0
