#!/usr/bin/env python3
"""Erzeugt kombinierte Evidence fuer Portfolio-Risk, Idempotency und Reconcile."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight  # noqa: E402
from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety  # noqa: E402
from shared_py.portfolio_risk_controls import (  # noqa: E402
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    build_portfolio_risk_summary_de,
    evaluate_portfolio_risk,
)
from shared_py.reconcile_truth import ReconcileTruthContext, evaluate_reconcile_truth  # noqa: E402

REQUIRED_LIVE_PREFLIGHT_REASONS = (
    "portfolio_risk_not_safe",
    "reconcile_not_ok",
    "unknown_order_state_active",
    "idempotency_key_missing",
    "safety_latch_active",
)


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=50_000.0,
        max_margin_usage=0.40,
        max_largest_position_risk=0.03,
        max_concurrent_positions=4,
        max_pending_orders=2,
        max_pending_live_candidates=1,
        max_net_directional_exposure=35_000.0,
        max_correlation_stress=0.75,
        max_funding_concentration=0.025,
        max_family_exposure=40_000.0,
    )


def _base_item(symbol: str = "BTCUSDT", notional: float = 10_000.0, side: str = "long") -> ExposureItem:
    return ExposureItem(
        symbol=symbol,
        market_family="futures",
        notional=notional,
        risk_pct=0.01,
        side=side,  # type: ignore[arg-type]
        funding_rate_abs=0.005,
        basis_bps_abs=10.0,
    )


def _portfolio_scenarios() -> dict[str, PortfolioSnapshot | None]:
    overloaded = [_base_item(f"BTC{i}USDT", 15_000.0) for i in range(5)]
    return {
        "missing_snapshot": None,
        "stale_snapshot": PortfolioSnapshot(
            open_positions=[_base_item()],
            pending_orders=[],
            pending_live_candidates=[],
            account_equity=100_000.0,
            used_margin=10_000.0,
            snapshot_fresh=False,
            correlation_stress=0.10,
            unknown_correlation=False,
        ),
        "limit_breach": PortfolioSnapshot(
            open_positions=overloaded,
            pending_orders=[_base_item("ETHUSDT", 30_000.0)],
            pending_live_candidates=[_base_item("SOLUSDT", 12_000.0), _base_item("XRPUSDT", 12_000.0)],
            account_equity=100_000.0,
            used_margin=65_000.0,
            snapshot_fresh=True,
            correlation_stress=0.90,
            unknown_correlation=False,
        ),
    }


def _order_scenarios() -> dict[str, OrderSubmitContext]:
    return {
        "idempotency_missing": OrderSubmitContext(
            execution_id="exec-1",
            idempotency_key=None,
            client_order_id=None,
            known_client_order_ids=set(),
            previous_state="submit_prepared",
            submit_result="ack",
        ),
        "duplicate_client_oid": OrderSubmitContext(
            execution_id="exec-2",
            idempotency_key="idem-2",
            client_order_id="cid-dup",
            known_client_order_ids={"cid-dup"},
            previous_state="submit_prepared",
            submit_result="ack",
        ),
        "unknown_submit_state_retry": OrderSubmitContext(
            execution_id="exec-3",
            idempotency_key="idem-3",
            client_order_id="cid-3",
            known_client_order_ids=set(),
            previous_state="unknown_submit_state",
            submit_result="ack",
        ),
        "timeout_sets_unknown": OrderSubmitContext(
            execution_id="exec-4",
            idempotency_key="idem-4",
            client_order_id="cid-4",
            known_client_order_ids=set(),
            previous_state="submit_prepared",
            submit_result="timeout",
        ),
        "db_failure_requires_reconcile": OrderSubmitContext(
            execution_id="exec-5",
            idempotency_key="idem-5",
            client_order_id="cid-5",
            known_client_order_ids=set(),
            previous_state="submit_prepared",
            submit_result="db_failure_after_submit",
        ),
        "retry_without_reconcile": OrderSubmitContext(
            execution_id="exec-6",
            idempotency_key="idem-6",
            client_order_id="cid-6",
            known_client_order_ids=set(),
            previous_state="reconcile_required",
            submit_result="ack",
        ),
    }


def _reconcile_scenarios() -> dict[str, ReconcileTruthContext]:
    base = dict(
        global_status="ok",
        per_asset_status={"BTCUSDT": "ok"},
        reconcile_fresh=True,
        exchange_reachable=True,
        auth_ok=True,
        unknown_order_state=False,
        position_mismatch=False,
        fill_mismatch=False,
        exchange_order_missing=False,
        local_order_missing=False,
        safety_latch_active=False,
    )
    return {
        "stale": ReconcileTruthContext(**{**base, "global_status": "stale", "reconcile_fresh": False}),
        "exchange_unreachable": ReconcileTruthContext(**{**base, "global_status": "exchange_unreachable", "exchange_reachable": False}),
        "auth_failed": ReconcileTruthContext(**{**base, "global_status": "auth_failed", "auth_ok": False}),
        "unknown_order_state": ReconcileTruthContext(**{**base, "global_status": "unknown_order_state", "unknown_order_state": True}),
        "position_mismatch": ReconcileTruthContext(**{**base, "global_status": "position_mismatch", "position_mismatch": True}),
        "fill_mismatch": ReconcileTruthContext(**{**base, "global_status": "fill_mismatch", "fill_mismatch": True}),
        "exchange_order_missing": ReconcileTruthContext(**{**base, "global_status": "exchange_order_missing", "exchange_order_missing": True}),
        "local_order_missing": ReconcileTruthContext(**{**base, "global_status": "local_order_missing", "local_order_missing": True}),
        "safety_latch_active": ReconcileTruthContext(**{**base, "global_status": "safety_latch_required", "safety_latch_active": True}),
    }


def _preflight_decision(
    *,
    portfolio_ok: bool,
    reconcile_ok: bool,
    idempotency_key: str | None,
    unknown_order_state: bool,
    safety_latch_active: bool,
) -> dict[str, Any]:
    decision = evaluate_live_preflight(
        LivePreflightContext(
            execution_mode_live=True,
            live_trade_enable=True,
            owner_approved=True,
            asset_in_catalog=True,
            asset_status_ok=True,
            asset_live_allowed=True,
            instrument_contract_complete=True,
            instrument_metadata_fresh=True,
            data_quality_status="pass",
            liquidity_status="pass",
            slippage_ok=True,
            risk_tier_live_allowed=True,
            order_sizing_ok=True,
            portfolio_risk_ok=portfolio_ok,
            strategy_evidence_ok=True,
            bitget_readiness_ok=True,
            reconcile_ok=reconcile_ok,
            kill_switch_active=False,
            safety_latch_active=safety_latch_active,
            unknown_order_state=unknown_order_state,
            account_snapshot_fresh=True,
            idempotency_key=idempotency_key,
            audit_context_present=True,
            checked_at="synthetic-risk-execution-evidence",
        )
    )
    return {
        "submit_allowed": decision.submit_allowed,
        "blocking_reasons": decision.blocking_reasons,
        "missing_gates": decision.missing_gates,
    }


def build_report_payload() -> dict[str, Any]:
    portfolio_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    reconcile_rows: list[dict[str, Any]] = []

    for name, snapshot in _portfolio_scenarios().items():
        result = evaluate_portfolio_risk(snapshot, _limits())
        portfolio_rows.append(
            {
                "id": name,
                "blocks_live": bool(result.block_reasons),
                "block_reasons": result.block_reasons,
                "cap_reasons": result.cap_reasons,
                "summary_de": build_portfolio_risk_summary_de(result),
                "preflight": _preflight_decision(
                    portfolio_ok=not bool(result.block_reasons),
                    reconcile_ok=True,
                    idempotency_key="idem-ok",
                    unknown_order_state=False,
                    safety_latch_active=False,
                ),
            }
        )

    for name, ctx in _order_scenarios().items():
        new_state, reasons = evaluate_submit_safety(ctx)
        idempotency_missing = "idempotency_fehlt" in reasons
        unknown_state = new_state == "unknown_submit_state" or "unknown_submit_state_blockiert_neue_openings" in reasons
        reconcile_not_ok = new_state == "reconcile_required" or "retry_ohne_reconcile_verboten" in reasons
        order_rows.append(
            {
                "id": name,
                "new_state": new_state,
                "block_reasons": reasons,
                "blocks_live": bool(reasons) or new_state in {"unknown_submit_state", "reconcile_required", "blocked"},
                "preflight": _preflight_decision(
                    portfolio_ok=True,
                    reconcile_ok=not reconcile_not_ok,
                    idempotency_key=None if idempotency_missing else "idem-ok",
                    unknown_order_state=unknown_state,
                    safety_latch_active="duplicate_client_order_id" in reasons,
                ),
            }
        )

    for name, ctx in _reconcile_scenarios().items():
        decision = evaluate_reconcile_truth(ctx)
        reconcile_rows.append(
            {
                "id": name,
                "status": decision.status,
                "block_reasons": decision.blocking_reasons,
                "warning_reasons": decision.warning_reasons,
                "reconcile_required": decision.reconcile_required,
                "safety_latch_required": decision.safety_latch_required,
                "blocks_live": bool(decision.blocking_reasons) or decision.reconcile_required,
                "preflight": _preflight_decision(
                    portfolio_ok=True,
                    reconcile_ok=decision.status == "ok",
                    idempotency_key="idem-ok",
                    unknown_order_state="unknown_order_state" in decision.blocking_reasons,
                    safety_latch_active=decision.safety_latch_required or "safety_latch_active" in decision.blocking_reasons,
                ),
            }
        )

    covered_live_preflight_reasons = sorted(
        {
            reason
            for row in [*portfolio_rows, *order_rows, *reconcile_rows]
            for reason in row["preflight"]["blocking_reasons"]
        }
    )
    missing_required = [
        reason for reason in REQUIRED_LIVE_PREFLIGHT_REASONS if reason not in covered_live_preflight_reasons
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "portfolio_scenarios": portfolio_rows,
        "order_idempotency_scenarios": order_rows,
        "reconcile_scenarios": reconcile_rows,
        "covered_live_preflight_reasons": covered_live_preflight_reasons,
        "missing_required_live_preflight_reasons": missing_required,
        "scenario_counts": {
            "portfolio": len(portfolio_rows),
            "order_idempotency": len(order_rows),
            "reconcile": len(reconcile_rows),
        },
        "notes": [
            "Synthetische Repo-Evidence ohne echte Orders und ohne Secrets.",
            "Portfolio-, Idempotency- und Reconcile-Fehler muessen vor Live-Submit denselben Live-Broker-Preflight blockieren.",
            "Externe Exchange-Truth-/Staging-Evidence bleibt fuer private Live erforderlich.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Risk Execution Evidence Report",
        "",
        "Status: synthetischer Fail-closed-Nachweis fuer Portfolio-Risk, Order-Idempotency und Reconcile-Safety.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private-Live-Entscheidung: `{payload['private_live_decision']}`",
        f"- Fehlende Required-Preflight-Blockgruende: `{len(payload['missing_required_live_preflight_reasons'])}`",
        "",
        "## Live-Broker-Preflight-Coverage",
        "",
        "- Abgedeckt: " + (", ".join(f"`{item}`" for item in payload["covered_live_preflight_reasons"]) or "-"),
        "- Fehlend: " + (", ".join(f"`{item}`" for item in payload["missing_required_live_preflight_reasons"]) or "-"),
        "",
        "## Portfolio-Risk",
        "",
    ]
    for row in payload["portfolio_scenarios"]:
        lines.append(f"- `{row['id']}`: blockiert=`{row['blocks_live']}`, Gruende={', '.join(row['block_reasons']) or '-'}")
    lines.extend(["", "## Order-Idempotency", ""])
    for row in payload["order_idempotency_scenarios"]:
        lines.append(f"- `{row['id']}`: state=`{row['new_state']}`, Gruende={', '.join(row['block_reasons']) or '-'}")
    lines.extend(["", "## Reconcile-Safety", ""])
    for row in payload["reconcile_scenarios"]:
        reasons = row["block_reasons"] or row["warning_reasons"]
        lines.append(f"- `{row['id']}`: status=`{row['status']}`, Gruende={', '.join(reasons) or '-'}")
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    payload = build_report_payload()
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "risk_execution_evidence_report: "
        f"portfolio={payload['scenario_counts']['portfolio']} "
        f"order_idempotency={payload['scenario_counts']['order_idempotency']} "
        f"reconcile={payload['scenario_counts']['reconcile']} "
        f"missing_required_preflight_reasons={len(payload['missing_required_live_preflight_reasons'])}"
    )
    if args.strict and payload["missing_required_live_preflight_reasons"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
