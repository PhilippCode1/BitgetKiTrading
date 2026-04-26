#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.reconcile_truth import (  # noqa: E402
    ReconcileTruthContext,
    build_reconcile_drift_reasons_de,
    evaluate_reconcile_truth,
)

RECONCILE_IDEMPOTENCY_SCHEMA_VERSION = "reconcile-idempotency-evidence-v1"
DEFAULT_EVIDENCE_TEMPLATE = ROOT / "docs" / "production_10_10" / "reconcile_idempotency_evidence.template.json"
SECRET_LIKE_KEYS = ("database_url", "dsn", "password", "secret", "token", "api_key", "private_key", "authorization")


def build_external_evidence_template() -> dict[str, Any]:
    return {
        "schema_version": RECONCILE_IDEMPOTENCY_SCHEMA_VERSION,
        "environment": "staging",
        "execution_mode": "shadow",
        "drill_started_at": "",
        "drill_completed_at": "",
        "git_sha": "",
        "operator": "",
        "evidence_reference": "",
        "exchange_truth_source": "",
        "reconcile_status": "PENDING",
        "reconcile_snapshot_fresh": False,
        "per_asset_reconcile_ok": false_dict(),
        "open_drift_count": None,
        "unknown_order_state_count": None,
        "position_mismatch_count": None,
        "fill_mismatch_count": None,
        "missing_exchange_ack_count": None,
        "retry_without_reconcile_blocked": False,
        "duplicate_client_oid_blocked": False,
        "idempotency_key_required": False,
        "timeout_sets_unknown_submit_state": False,
        "unknown_submit_state_blocks_opening": False,
        "db_failure_after_submit_requires_reconcile": False,
        "safety_latch_armed_on_unresolved_duplicate": False,
        "audit_trail_verified": False,
        "alert_delivery_verified": False,
        "main_console_reconcile_state_verified": False,
        "live_write_allowed_during_drill": False,
        "real_exchange_order_sent": False,
        "owner_signoff": False,
        "database_url": "[REDACTED]",
        "authorization": "[REDACTED]",
        "notes_de": "Template: echten Staging-/Shadow-Reconcile-/Idempotency-Drill extern ausfuehren; Secrets niemals im Repo speichern.",
    }


def false_dict() -> dict[str, str]:
    return {}


def secret_surface_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def _non_negative_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def assess_external_evidence(payload: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    if not payload:
        return "FAIL", ["reconcile_idempotency_evidence_missing"], []
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != RECONCILE_IDEMPOTENCY_SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if payload.get("environment") not in {"staging", "shadow", "production_shadow"}:
        blockers.append("environment_invalid")
    if payload.get("execution_mode") not in {"shadow", "paper"}:
        blockers.append("execution_mode_not_non_live")
    for key, code in (
        ("drill_started_at", "drill_started_at_missing"),
        ("drill_completed_at", "drill_completed_at_missing"),
        ("git_sha", "git_sha_missing"),
        ("operator", "operator_missing"),
        ("evidence_reference", "evidence_reference_missing"),
        ("exchange_truth_source", "exchange_truth_source_missing"),
    ):
        if not str(payload.get(key) or "").strip():
            blockers.append(code)
    if payload.get("reconcile_status") != "ok":
        blockers.append("reconcile_status_not_ok")
    if payload.get("reconcile_snapshot_fresh") is not True:
        blockers.append("reconcile_snapshot_not_fresh")
    per_asset = payload.get("per_asset_reconcile_ok")
    if not isinstance(per_asset, dict) or not per_asset:
        blockers.append("per_asset_reconcile_missing")
    elif any(value is not True for value in per_asset.values()):
        blockers.append("per_asset_reconcile_not_all_ok")
    zero_counts = (
        ("open_drift_count", "open_drift_present"),
        ("unknown_order_state_count", "unknown_order_state_present"),
        ("position_mismatch_count", "position_mismatch_present"),
        ("fill_mismatch_count", "fill_mismatch_present"),
        ("missing_exchange_ack_count", "missing_exchange_ack_present"),
    )
    for key, code in zero_counts:
        value = _non_negative_int(payload, key)
        if value is None or value > 0:
            blockers.append(code)
    required_true = (
        ("retry_without_reconcile_blocked", "retry_without_reconcile_not_blocked"),
        ("duplicate_client_oid_blocked", "duplicate_client_oid_not_blocked"),
        ("idempotency_key_required", "idempotency_key_not_required"),
        ("timeout_sets_unknown_submit_state", "timeout_unknown_state_not_set"),
        ("unknown_submit_state_blocks_opening", "unknown_submit_state_not_blocking"),
        ("db_failure_after_submit_requires_reconcile", "db_failure_reconcile_not_required"),
        ("safety_latch_armed_on_unresolved_duplicate", "safety_latch_not_armed_on_unresolved_duplicate"),
        ("audit_trail_verified", "audit_trail_not_verified"),
        ("alert_delivery_verified", "alert_delivery_not_verified"),
        ("main_console_reconcile_state_verified", "main_console_reconcile_state_not_verified"),
    )
    for key, code in required_true:
        if payload.get(key) is not True:
            blockers.append(code)
    if payload.get("live_write_allowed_during_drill") is not False:
        blockers.append("live_write_allowed_during_drill")
    if payload.get("real_exchange_order_sent") is not False:
        blockers.append("real_exchange_order_sent")
    if payload.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return status, blockers, warnings


def _external_markdown(payload: dict[str, Any], status: str, blockers: list[str], warnings: list[str], secret_issues: list[str]) -> str:
    lines = [
        "# Reconcile / Order-Idempotency Evidence Check",
        "",
        "Status: prueft externen Reconcile-/Exchange-Truth-/Idempotency-Nachweis ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Execution Mode: `{payload.get('execution_mode')}`",
        f"- Git SHA: `{payload.get('git_sha') or 'missing'}`",
        f"- Operator: `{payload.get('operator') or 'missing'}`",
        f"- Reconcile Status: `{payload.get('reconcile_status')}`",
        f"- Exchange Truth Source: `{payload.get('exchange_truth_source') or 'missing'}`",
        f"- Ergebnis: `{status}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in blockers)
    if not blockers:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in warnings)
    if not warnings:
        lines.append("- Keine Warnings.")
    lines.extend(["", "## Secret-Surface"])
    lines.extend(f"- `{item}`" for item in secret_issues)
    if not secret_issues:
        lines.append("- Keine unredigierten Secret-Felder erkannt.")
    lines.extend(
        [
            "",
            "## Einordnung",
            "",
            "- Simulierte Reconcile-Drills sind Code-Evidence, aber keine Live-Freigabe.",
            "- Live bleibt `NO_GO`, bis Exchange-Truth, Idempotency-Retry-Pfade, Audit, Alert und Owner-Signoff extern belegt sind.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_simulated_cases() -> list[tuple[str, ReconcileTruthContext]]:
    base = dict(
        global_status="ok",
        per_asset_status={"BTCUSDT": "ok", "ETHUSDT": "ok"},
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
    return [
        ("exchange_order_missing", ReconcileTruthContext(**{**base, "exchange_order_missing": True, "global_status": "exchange_order_missing"})),
        ("local_order_missing", ReconcileTruthContext(**{**base, "local_order_missing": True, "global_status": "local_order_missing"})),
        ("position_mismatch", ReconcileTruthContext(**{**base, "position_mismatch": True, "global_status": "position_mismatch"})),
        ("stale_reconcile", ReconcileTruthContext(**{**base, "reconcile_fresh": False, "global_status": "stale"})),
        ("unknown_order_state", ReconcileTruthContext(**{**base, "unknown_order_state": True, "global_status": "unknown_order_state"})),
        ("safety_latch_required", ReconcileTruthContext(**{**base, "fill_mismatch": True, "global_status": "fill_mismatch"})),
    ]


def _report_markdown() -> str:
    lines = ["# Reconcile-Truth-Drill (simulated)", ""]
    for name, ctx in _build_simulated_cases():
        decision = evaluate_reconcile_truth(ctx)
        reasons = build_reconcile_drift_reasons_de(decision)
        lines.extend(
            [
                f"## Szenario: {name}",
                f"- Ergebnisstatus: {decision.status}",
                f"- Reconcile required: {decision.reconcile_required}",
                f"- Safety-Latch required: {decision.safety_latch_required}",
                f"- Main-Console-Status: {'BLOCKIERT' if decision.blocking_reasons else 'WARNUNG/OK'}",
                f"- Gruende: {', '.join(reasons)}",
                "",
            ]
        )
    return "\n".join(lines)


def _simulated_payload() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, ctx in _build_simulated_cases():
        decision = evaluate_reconcile_truth(ctx)
        rows.append(
            {
                "scenario": name,
                "status": decision.status,
                "reconcile_required": decision.reconcile_required,
                "safety_latch_required": decision.safety_latch_required,
                "blocking_reasons": decision.blocking_reasons,
                "warning_reasons": decision.warning_reasons,
                "evidence_level": "synthetic",
                "live_allowed": False,
            }
        )
    return {
        "status": "implemented",
        "decision": "NOT_ENOUGH_EVIDENCE",
        "verified": False,
        "evidence_level": "synthetic",
        "scenarios": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile/Exchange-Truth Drill")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", default="simulated")
    parser.add_argument("--output-md", default="reports/reconcile_truth_drill.md")
    parser.add_argument("--evidence-json", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_evidence_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_template}")
        return 0
    if args.evidence_json:
        loaded = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Evidence root muss ein JSON-Objekt sein.")
        status, blockers, warnings = assess_external_evidence(loaded)
        secret_issues = secret_surface_issues(loaded)
        payload = {
            "ok": status == "PASS" and not secret_issues,
            "status": status,
            "blockers": blockers + secret_issues,
            "warnings": warnings,
        }
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_external_markdown(loaded, status, blockers, warnings, secret_issues), encoding="utf-8")
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        print(_external_markdown(loaded, status, blockers, warnings, secret_issues), end="")
        return 1 if args.strict and not payload["ok"] else 0
    if args.mode != "simulated":
        raise SystemExit("Nur --mode simulated ist lokal erlaubt.")
    if args.dry_run:
        payload = _simulated_payload()
        out_md = Path(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(_report_markdown(), encoding="utf-8")
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print("reconcile_truth_drill: dry-run ok (mode=simulated)")
        return 0
    out = Path(args.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_report_markdown(), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(_simulated_payload(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"reconcile_truth_drill: ok (mode=simulated, output={out.as_posix()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
