#!/usr/bin/env python3
"""Erzeugt Evidence fuer Main-Console-Safety-State und Audit/Forensics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.audit_contracts import (  # noqa: E402
    build_german_forensic_summary,
    build_private_audit_event,
    payload_contains_secret_markers,
)
from shared_py.main_console_safety import (  # noqa: E402
    SafetyCenterSnapshot,
    live_blocked_by_safety_center,
)

REQUIRED_VISIBLE_GATES = (
    "reconcile",
    "exchange_truth",
    "kill_switch",
    "safety_latch",
    "backend",
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


def _snapshot_scenarios() -> dict[str, SafetyCenterSnapshot]:
    return {
        "reconcile_unknown": SafetyCenterSnapshot(
            reconcile_status="unknown",
            kill_switch_active=False,
            safety_latch_active=False,
            exchange_truth_status="vorhanden",
            backend_connected=True,
        ),
        "exchange_truth_missing": SafetyCenterSnapshot(
            reconcile_status="ok",
            kill_switch_active=False,
            safety_latch_active=False,
            exchange_truth_status="fehlt",
            backend_connected=True,
        ),
        "kill_switch_active": SafetyCenterSnapshot(
            reconcile_status="ok",
            kill_switch_active=True,
            safety_latch_active=False,
            exchange_truth_status="vorhanden",
            backend_connected=True,
        ),
        "safety_latch_active": SafetyCenterSnapshot(
            reconcile_status="ok",
            kill_switch_active=False,
            safety_latch_active=True,
            exchange_truth_status="vorhanden",
            backend_connected=True,
        ),
        "backend_unavailable": SafetyCenterSnapshot(
            reconcile_status="ok",
            kill_switch_active=False,
            safety_latch_active=False,
            exchange_truth_status="vorhanden",
            backend_connected=False,
        ),
    }


def _visible_gate_states(snapshot: SafetyCenterSnapshot) -> dict[str, str]:
    return {
        "reconcile": snapshot.reconcile_status,
        "exchange_truth": snapshot.exchange_truth_status,
        "kill_switch": "active" if snapshot.kill_switch_active else "inactive",
        "safety_latch": "active" if snapshot.safety_latch_active else "inactive",
        "backend": "connected" if snapshot.backend_connected else "unavailable",
    }


def _blocking_reasons(snapshot: SafetyCenterSnapshot) -> list[str]:
    reasons: list[str] = []
    if snapshot.reconcile_status in {"unknown", "stale", "fail"}:
        reasons.append("reconcile_status_blocks_live")
    if snapshot.exchange_truth_status in {"unknown", "stale", "fehlt", "not_checked"}:
        reasons.append("exchange_truth_blocks_live")
    if snapshot.kill_switch_active:
        reasons.append("kill_switch_blocks_live")
    if snapshot.safety_latch_active:
        reasons.append("safety_latch_blocks_live")
    if not snapshot.backend_connected:
        reasons.append("backend_unavailable_blocks_live")
    return reasons


def _reason_text_de(reasons: list[str]) -> str:
    mapping = {
        "reconcile_status_blocks_live": "Reconcile ist unklar oder fehlerhaft; Live bleibt verboten.",
        "exchange_truth_blocks_live": "Exchange-Truth fehlt oder ist stale; Live bleibt verboten.",
        "kill_switch_blocks_live": "Kill-Switch ist aktiv; echte Orders sind gesperrt.",
        "safety_latch_blocks_live": "Safety-Latch ist aktiv; Submit/Replace bleibt gesperrt.",
        "backend_unavailable_blocks_live": "Backend ist nicht verbunden; Safety-State ist nicht belastbar und Live bleibt verboten.",
    }
    return " ".join(mapping.get(reason, reason) for reason in reasons)


def _audit_event(*, scenario_id: str, git_sha: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "event_id": f"main-console-safety-{scenario_id}",
        "event_type": "private_decision_audit",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "git_sha": git_sha,
        "service": "main-console",
        "asset_symbol": "ALL",
        "market_family": "multi_asset",
        "product_type": "private-main-console",
        "margin_coin": "USDT",
        "decision_type": "live_decision",
        "decision": "do_not_trade",
        "reason_codes": reasons,
        "reason_text_de": _reason_text_de(reasons),
        "risk_tier": "portfolio",
        "liquidity_tier": "not_applicable",
        "data_quality_status": "not_applicable",
        "exchange_truth_status": "blocked" if "exchange_truth_blocks_live" in reasons else "checked_or_not_applicable",
        "reconcile_status": "blocked" if "reconcile_status_blocks_live" in reasons else "checked_or_not_applicable",
        "operator_context": "philipp",
        "trace_id": f"trace-{scenario_id}",
        "correlation_id": f"corr-{scenario_id}",
        "no_secrets_confirmed": True,
    }


def build_report_payload() -> dict[str, Any]:
    git_sha = _git_sha()
    scenarios: list[dict[str, Any]] = []
    visible_gate_coverage: set[str] = set()
    audit_valid_count = 0
    secret_safe = True

    for scenario_id, snapshot in _snapshot_scenarios().items():
        gates = _visible_gate_states(snapshot)
        visible_gate_coverage.update(gates)
        reasons = _blocking_reasons(snapshot)
        blocked = live_blocked_by_safety_center(snapshot)
        event = _audit_event(scenario_id=scenario_id, git_sha=git_sha, reasons=reasons)
        audit = build_private_audit_event(event)
        audit_valid = bool(audit["validation"]["valid"])
        audit_valid_count += 1 if audit_valid else 0
        summary_de = build_german_forensic_summary(event)
        if payload_contains_secret_markers(audit):
            secret_safe = False
        scenarios.append(
            {
                "id": scenario_id,
                "visible_gate_states": gates,
                "real_orders_possible": False,
                "private_live_allowed": "NO_GO",
                "blocked_by_safety_center": blocked,
                "blocking_reasons": reasons,
                "reason_text_de": _reason_text_de(reasons),
                "audit_valid": audit_valid,
                "audit_errors": audit["validation"]["errors"],
                "forensic_summary_de": summary_de,
            }
        )

    missing_visible_gates = [gate for gate in REQUIRED_VISIBLE_GATES if gate not in visible_gate_coverage]
    blocking_failures = [
        row["id"]
        for row in scenarios
        if row["private_live_allowed"] != "NO_GO"
        or row["real_orders_possible"] is not False
        or row["blocked_by_safety_center"] is not True
        or not row["blocking_reasons"]
        or row["audit_valid"] is not True
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": git_sha,
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "scenario_count": len(scenarios),
        "audit_valid_count": audit_valid_count,
        "secret_safe": secret_safe,
        "missing_visible_gates": missing_visible_gates,
        "blocking_failures": blocking_failures,
        "scenarios": scenarios,
        "notes": [
            "Synthetische Repo-Evidence ohne echte Orders und ohne Secrets.",
            "Main Console muss Live-Verbote, blockierende Gates und deutsche Forensics-Texte sichtbar machen.",
            "Dieser Report ersetzt keine externe Shadow-, Bitget-, Alert- oder Owner-Signoff-Evidence.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Main Console Safety / Audit Evidence Report",
        "",
        "Status: synthetischer Nachweis fuer ehrliche Operator-Sicht, Live-NO-GO und Audit/Forensics.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Szenarien: `{payload['scenario_count']}`",
        f"- Audit valide: `{payload['audit_valid_count']}`",
        f"- Secret-safe: `{payload['secret_safe']}`",
        f"- Fehlende sichtbare Gates: `{len(payload['missing_visible_gates'])}`",
        f"- Blocking-Failures: `{len(payload['blocking_failures'])}`",
        "",
        "## Szenarien",
        "",
        "| Szenario | Private Live | Echte Orders moeglich | Blockgruende | Deutscher Operator-Text | Audit valide |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        reasons = ", ".join(f"`{item}`" for item in row["blocking_reasons"]) or "-"
        lines.append(
            f"| `{row['id']}` | `{row['private_live_allowed']}` | `{row['real_orders_possible']}` | "
            f"{reasons} | {row['reason_text_de']} | `{row['audit_valid']}` |"
        )
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
        "main_console_safety_audit_report: "
        f"scenarios={payload['scenario_count']} "
        f"audit_valid={payload['audit_valid_count']} "
        f"missing_visible_gates={len(payload['missing_visible_gates'])} "
        f"blocking_failures={len(payload['blocking_failures'])}"
    )
    if args.strict and (
        payload["missing_visible_gates"]
        or payload["blocking_failures"]
        or payload["secret_safe"] is not True
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
