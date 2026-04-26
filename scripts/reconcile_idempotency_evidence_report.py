#!/usr/bin/env python3
"""Kombinierter Reconcile-/Order-Idempotency-Evidence-Report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_truth_drill import (  # noqa: E402
    DEFAULT_EVIDENCE_TEMPLATE,
    assess_external_evidence,
    secret_surface_issues,
)
from scripts.risk_execution_evidence_report import (  # noqa: E402
    REQUIRED_LIVE_PREFLIGHT_REASONS,
    build_report_payload as build_risk_execution_payload,
)

REQUIRED_EXTERNAL_BLOCKERS = (
    "reconcile_status_not_ok",
    "reconcile_snapshot_not_fresh",
    "per_asset_reconcile_missing",
    "open_drift_present",
    "unknown_order_state_present",
    "position_mismatch_present",
    "fill_mismatch_present",
    "missing_exchange_ack_present",
    "retry_without_reconcile_not_blocked",
    "duplicate_client_oid_not_blocked",
    "idempotency_key_not_required",
    "timeout_unknown_state_not_set",
    "unknown_submit_state_not_blocking",
    "db_failure_reconcile_not_required",
    "safety_latch_not_armed_on_unresolved_duplicate",
    "audit_trail_not_verified",
    "alert_delivery_not_verified",
    "main_console_reconcile_state_not_verified",
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


def _load_template() -> dict[str, Any]:
    loaded = json.loads(DEFAULT_EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{DEFAULT_EVIDENCE_TEMPLATE} muss ein JSON-Objekt enthalten.")
    return loaded


def _order_scenario_assertions(risk_payload: dict[str, Any]) -> dict[str, Any]:
    rows = {row["id"]: row for row in risk_payload["order_idempotency_scenarios"]}
    expected = {
        "idempotency_missing": "idempotency_fehlt",
        "duplicate_client_oid": "duplicate_client_order_id",
        "unknown_submit_state_retry": "unknown_submit_state_blockiert_neue_openings",
        "timeout_sets_unknown": "submit_timeout_unknown_state",
        "db_failure_requires_reconcile": "db_failure_reconcile_required",
        "retry_without_reconcile": "retry_ohne_reconcile_verboten",
    }
    missing: list[str] = []
    for scenario_id, reason in expected.items():
        row = rows.get(scenario_id)
        if row is None:
            missing.append(f"scenario_missing:{scenario_id}")
            continue
        reasons = set(row.get("block_reasons") or [])
        if reason not in reasons:
            missing.append(f"reason_missing:{scenario_id}:{reason}")
        if row.get("blocks_live") is not True:
            missing.append(f"scenario_not_live_blocking:{scenario_id}")
        if row.get("preflight", {}).get("submit_allowed") is not False:
            missing.append(f"preflight_not_blocking:{scenario_id}")
    return {
        "expected_count": len(expected),
        "scenario_count": len(rows),
        "missing_assertions": missing,
    }


def _reconcile_scenario_assertions(risk_payload: dict[str, Any]) -> dict[str, Any]:
    rows = {row["id"]: row for row in risk_payload["reconcile_scenarios"]}
    expected = {
        "stale",
        "exchange_unreachable",
        "auth_failed",
        "unknown_order_state",
        "position_mismatch",
        "fill_mismatch",
        "exchange_order_missing",
        "local_order_missing",
        "safety_latch_active",
    }
    missing: list[str] = []
    for scenario_id in sorted(expected):
        row = rows.get(scenario_id)
        if row is None:
            missing.append(f"scenario_missing:{scenario_id}")
            continue
        if row.get("blocks_live") is not True:
            missing.append(f"scenario_not_live_blocking:{scenario_id}")
        if row.get("preflight", {}).get("submit_allowed") is not False:
            missing.append(f"preflight_not_blocking:{scenario_id}")
    return {
        "expected_count": len(expected),
        "scenario_count": len(rows),
        "missing_assertions": missing,
    }


def build_report_payload() -> dict[str, Any]:
    template = _load_template()
    status, blockers, warnings = assess_external_evidence(template)
    secret_issues = secret_surface_issues(template)
    risk_payload = build_risk_execution_payload()
    missing_external_blockers = sorted(set(REQUIRED_EXTERNAL_BLOCKERS) - set(blockers))
    missing_live_preflight = list(risk_payload["missing_required_live_preflight_reasons"])
    order_assertions = _order_scenario_assertions(risk_payload)
    reconcile_assertions = _reconcile_scenario_assertions(risk_payload)

    failures: list[str] = []
    if status != "FAIL":
        failures.append("external_template_must_fail_until_real_reconcile_evidence")
    if secret_issues:
        failures.append("unredacted_secret_surface_detected")
    if missing_external_blockers:
        failures.append("external_template_missing_required_blocker_coverage")
    if missing_live_preflight:
        failures.append("risk_execution_missing_required_live_preflight_reasons")
    if order_assertions["missing_assertions"]:
        failures.append("order_idempotency_scenario_assertions_missing")
    if reconcile_assertions["missing_assertions"]:
        failures.append("reconcile_scenario_assertions_missing")

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "external_template": {
            "path": str(DEFAULT_EVIDENCE_TEMPLATE.relative_to(ROOT)),
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "secret_surface_issues": secret_issues,
            "missing_required_blockers": missing_external_blockers,
        },
        "risk_execution": {
            "scenario_counts": risk_payload["scenario_counts"],
            "covered_live_preflight_reasons": risk_payload["covered_live_preflight_reasons"],
            "required_live_preflight_reasons": list(REQUIRED_LIVE_PREFLIGHT_REASONS),
            "missing_required_live_preflight_reasons": missing_live_preflight,
            "private_live_decision": risk_payload["private_live_decision"],
        },
        "order_idempotency_assertions": order_assertions,
        "reconcile_assertions": reconcile_assertions,
        "external_required": [
            "real_exchange_truth_reconcile_drill_missing",
            "staging_duplicate_client_oid_drill_missing",
            "timeout_and_db_failure_reconcile_drill_missing",
            "audit_alert_main_console_reconcile_evidence_missing",
            "owner_signed_reconcile_idempotency_acceptance_missing",
        ],
        "failures": failures,
        "notes": [
            "Dieser Report kombiniert externe Template-Pruefung und synthetische Live-Preflight-Coverage.",
            "Ein PASS des Repo-Templates ohne echte Staging-/Shadow-Evidence waere ein Fehler.",
            "Private Live bleibt blockiert, bis Exchange-Truth, Retry-/Duplicate-Pfade, Audit, Alert und Owner-Signoff extern belegt sind.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Reconcile / Order-Idempotency Evidence Report",
        "",
        "Status: kombinierter repo-lokaler Nachweis fuer Reconcile-Safety und Order-Idempotency ohne echte Exchange-Orders.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- External Required: `{len(payload['external_required'])}`",
        f"- External Template Status: `{payload['external_template']['status']}`",
        f"- External Template Blocker: `{len(payload['external_template']['blockers'])}`",
        "",
        "## Live-Broker-Preflight-Coverage",
        "",
        "- Abgedeckt: "
        + (
            ", ".join(f"`{item}`" for item in payload["risk_execution"]["covered_live_preflight_reasons"])
            or "-"
        ),
        "- Fehlend: "
        + (
            ", ".join(
                f"`{item}`" for item in payload["risk_execution"]["missing_required_live_preflight_reasons"]
            )
            or "-"
        ),
        "",
        "## Assertions",
        "",
        f"- Order-Idempotency fehlende Assertions: `{len(payload['order_idempotency_assertions']['missing_assertions'])}`",
        f"- Reconcile fehlende Assertions: `{len(payload['reconcile_assertions']['missing_assertions'])}`",
        f"- Secret-Surface-Issues: `{len(payload['external_template']['secret_surface_issues'])}`",
        f"- Fehlende externe Pflichtblocker-Abdeckung: `{len(payload['external_template']['missing_required_blockers'])}`",
        "",
        "## External Required",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload["external_required"])
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
        "reconcile_idempotency_evidence_report: "
        f"failures={len(payload['failures'])} "
        f"external_required={len(payload['external_required'])} "
        f"private_live={payload['private_live_decision']}"
    )
    if args.strict and payload["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
