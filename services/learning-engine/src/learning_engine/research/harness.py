"""Orchestriert Benchmark-Reports aus DB-Stichproben."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from shared_py.replay_determinism import FLOAT_METRICS_RTOL

from learning_engine.research.baseline_policies import (
    BASELINE_REGISTRY,
    compute_baseline_vector,
)
from learning_engine.research.benchmark_metrics import (
    aggregate_system_trade_metrics,
    take_decision_metrics,
)
from learning_engine.research.counterfactual import (
    build_counterfactual_scenarios,
    summarize_lane_outcomes,
)
from learning_engine.training.constants import TRAINING_PIPELINE_VERSION


def _eval_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    return (int(row.get("decision_ts_ms") or 0), str(row.get("evaluation_id") or ""))


def _contract_version_key(row: dict[str, Any]) -> str:
    mc = row.get("model_contract_json")
    if isinstance(mc, dict):
        v = mc.get("feature_schema_version") or mc.get("model_contract_version")
        if v is not None and str(v).strip():
            return str(v).strip()
    return "_unknown"


def _build_model_contract_slices(
    rows: list[dict[str, Any]],
    *,
    min_rows_per_slice: int,
) -> dict[str, Any]:
    by_v: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_v[_contract_version_key(r)].append(r)
    out: dict[str, Any] = {}
    for k in sorted(by_v.keys()):
        sub = by_v[k]
        if len(sub) < min_rows_per_slice:
            continue
        sub.sort(key=_eval_sort_key)
        st = [1 if bool(r.get("take_trade_label")) else 0 for r in sub]
        out[k] = {
            "n": len(sub),
            "system_vs_take_trade_label": take_decision_metrics(
                sub,
                st,
                name="system_take_trade_label_proxy",
            ),
        }
    return out


def build_benchmark_evidence_report(
    *,
    evaluation_rows: list[dict[str, Any]],
    limit_evaluations: int,
    limit_e2e: int,
    e2e_rows: list[dict[str, Any]] | None = None,
    symbol_filter: str | None = None,
    min_rows_model_contract_slice: int = 20,
) -> dict[str, Any]:
    lim_ev = max(1, min(int(limit_evaluations), 50_000))
    lim_e2 = max(1, min(int(limit_e2e), 20_000))
    rows = list(evaluation_rows)[:lim_ev]
    rows.sort(key=_eval_sort_key)

    system_take = [1 if bool(r.get("take_trade_label")) else 0 for r in rows]
    system_metrics = take_decision_metrics(
        rows,
        system_take,
        name="system_take_trade_label_proxy",
    )
    agg_trades = aggregate_system_trade_metrics(rows)

    baselines: dict[str, Any] = {}
    for name in sorted(BASELINE_REGISTRY.keys()):
        preds = [compute_baseline_vector(r)[name] for r in rows]
        baselines[name] = take_decision_metrics(rows, preds, name=name)

    cf_samples: list[dict[str, Any]] = []
    lane_rows: list[dict[str, Any]] = []
    e2e_use = list(e2e_rows or [])[:lim_e2]
    if e2e_use:
        for er in e2e_use:
            snap_raw = er.get("snapshot_json")
            if isinstance(snap_raw, str):
                try:
                    snap = json.loads(snap_raw)
                except json.JSONDecodeError:
                    snap = {}
            else:
                snap = snap_raw if isinstance(snap_raw, dict) else {}
            scenarios = build_counterfactual_scenarios(snap)
            if scenarios:
                cf_samples.append(
                    {
                        "signal_id": str(er.get("signal_id")),
                        "decision_ts_ms": er.get("decision_ts_ms"),
                        "counterfactual_scenarios": scenarios,
                    }
                )
            lane = summarize_lane_outcomes(er)
            if lane:
                lane_rows.append(lane)

    version_slices = _build_model_contract_slices(
        rows,
        min_rows_per_slice=max(5, int(min_rows_model_contract_slice)),
    )

    return {
        "report_schema_version": "research-benchmark-evidence-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "training_pipeline_version_ref": TRAINING_PIPELINE_VERSION,
        "symbol_filter": symbol_filter.upper() if symbol_filter else None,
        "sample_limits": {"evaluations": lim_ev, "e2e": lim_e2},
        "evaluation_row_count": len(rows),
        "aggregate_trade_metrics_all_closed_evals": agg_trades,
        "system_vs_take_trade_label": system_metrics,
        "baselines_vs_take_trade_label": baselines,
        "by_model_contract_feature_schema_version": version_slices,
        "counterfactual_specimens": cf_samples[:50],
        "lane_comparison_closed_pnl": {
            "rows_with_any_closed_pnl": len(lane_rows),
            "samples": lane_rows[:100],
        },
        "determinism": {
            "evaluation_row_order": "sorted_by_decision_ts_ms_asc_then_evaluation_id",
            "database_sample_order": (
                "newest_first_then_resorted_chronologically_in_harness"
            ),
            "float_metrics_rtol": FLOAT_METRICS_RTOL,
            "non_deterministic_factors_de": [
                "generated_at_utc (Wanduhr)",
                (
                    "Gleitkomma-Aggregate koennen je nach CPU/BLAS minimal abweichen; "
                    "Vergleich mit FLOAT_METRICS_RTOL"
                ),
                (
                    "Fehlende Snapshots aendern Baselines und "
                    "Fehlklassifikationen in Heuristiken"
                ),
                (
                    "DB-Replikas: selten marginale Stichprobenrandfaelle "
                    "je nach Lesezeitpunkt"
                ),
            ],
        },
        "interpretation_de": (
            "take_trade_label ist Lernziel aus abgeschlossenen Trades; "
            "Baselines sind heuristische Vorhersagen ohne Meta-Modell. "
            "Vergleich dient Evidenz, nicht Live-ersetzender Strategie."
        ),
    }


def _json_pretty(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def report_to_markdown(report: dict[str, Any]) -> str:
    agg = report.get("aggregate_trade_metrics_all_closed_evals")
    sys_m = report.get("system_vs_take_trade_label")
    base = report.get("baselines_vs_take_trade_label")
    slices = report.get("by_model_contract_feature_schema_version")
    det = report.get("determinism")
    lines = [
        "# Research Benchmark Evidence",
        "",
        f"- Erzeugt: `{report.get('generated_at_utc')}`",
        f"- Evaluations: **{report.get('evaluation_row_count')}**",
        "",
        "## Aggregat (alle Zeilen)",
        "",
        "```json",
        _json_pretty(agg),
        "```",
        "",
        "## System (take_trade_label Proxy)",
        "",
        "```json",
        _json_pretty(sys_m),
        "```",
        "",
        "## Baselines",
        "",
        "```json",
        _json_pretty(base),
        "```",
        "",
        "## Modellvertrag-Slices (feature_schema_version)",
        "",
        "```json",
        _json_pretty(slices),
        "```",
        "",
        "## Determinismus (Report-Meta)",
        "",
        "```json",
        _json_pretty(det),
        "```",
        "",
    ]
    return "\n".join(lines)
