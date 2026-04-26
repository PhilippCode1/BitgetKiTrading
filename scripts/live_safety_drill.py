#!/usr/bin/env python3
"""Simulated live safety drill evidence, without exchange writes."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SAFETY_DRILL_SCHEMA_VERSION = "live-safety-drill-evidence-v1"
DEFAULT_DRILL_TEMPLATE = ROOT / "docs" / "production_10_10" / "live_safety_drill.template.json"
SECRET_LIKE_KEYS = ("database_url", "dsn", "password", "secret", "token", "api_key", "private_key", "authorization")


@dataclass(frozen=True)
class SafetyDrillEvidence:
    generated_at: str
    git_sha: str
    mode: str
    kill_switch_active: bool
    safety_latch_active: bool
    opening_order_blocked_by_kill_switch: bool
    opening_order_blocked_by_safety_latch: bool
    emergency_flatten_reduce_only: bool
    emergency_flatten_safe: bool
    audit_expected: bool
    alert_expected: bool
    go_no_go: str
    live_write_allowed: bool


@dataclass(frozen=True)
class ExternalSafetyDrillAssessment:
    status: str
    blockers: list[str]
    warnings: list[str]


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def build_external_drill_template() -> dict[str, Any]:
    return {
        "schema_version": SAFETY_DRILL_SCHEMA_VERSION,
        "environment": "staging",
        "execution_mode": "shadow",
        "drill_started_at": "",
        "drill_completed_at": "",
        "git_sha": "",
        "operator": "",
        "evidence_reference": "",
        "kill_switch_arm_verified": False,
        "kill_switch_blocks_opening_submit": False,
        "kill_switch_release_requires_operator": False,
        "safety_latch_arm_verified": False,
        "safety_latch_blocks_submit": False,
        "safety_latch_blocks_replace": False,
        "safety_latch_release_requires_reason": False,
        "emergency_flatten_tested": False,
        "emergency_flatten_reduce_only": False,
        "emergency_flatten_exchange_truth_checked": False,
        "emergency_flatten_no_increase_only": False,
        "cancel_all_tested": False,
        "audit_trail_verified": False,
        "alert_delivery_verified": False,
        "main_console_state_verified": False,
        "reconcile_after_drill_status": "",
        "live_write_allowed_during_drill": False,
        "real_exchange_order_sent": False,
        "owner_signoff": False,
        "database_url": "[REDACTED]",
        "authorization": "[REDACTED]",
        "notes_de": "Template: echten Staging-/Shadow-Safety-Drill extern ausfuehren; Secrets niemals im Repo speichern.",
    }


def secret_surface_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def assess_external_safety_drill(payload: dict[str, Any] | None) -> ExternalSafetyDrillAssessment:
    if not payload:
        return ExternalSafetyDrillAssessment("FAIL", ["safety_drill_evidence_missing"], [])
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SAFETY_DRILL_SCHEMA_VERSION:
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
    ):
        if not str(payload.get(key) or "").strip():
            blockers.append(code)
    required_true = (
        ("kill_switch_arm_verified", "kill_switch_arm_not_verified"),
        ("kill_switch_blocks_opening_submit", "kill_switch_opening_submit_not_blocked"),
        ("kill_switch_release_requires_operator", "kill_switch_release_not_operator_gated"),
        ("safety_latch_arm_verified", "safety_latch_arm_not_verified"),
        ("safety_latch_blocks_submit", "safety_latch_submit_not_blocked"),
        ("safety_latch_blocks_replace", "safety_latch_replace_not_blocked"),
        ("safety_latch_release_requires_reason", "safety_latch_release_reason_not_required"),
        ("emergency_flatten_tested", "emergency_flatten_not_tested"),
        ("emergency_flatten_reduce_only", "emergency_flatten_not_reduce_only"),
        ("emergency_flatten_exchange_truth_checked", "emergency_flatten_exchange_truth_not_checked"),
        ("emergency_flatten_no_increase_only", "emergency_flatten_no_increase_not_confirmed"),
        ("cancel_all_tested", "cancel_all_not_tested"),
        ("audit_trail_verified", "audit_trail_not_verified"),
        ("alert_delivery_verified", "alert_delivery_not_verified"),
        ("main_console_state_verified", "main_console_state_not_verified"),
    )
    for key, code in required_true:
        if payload.get(key) is not True:
            blockers.append(code)
    if payload.get("reconcile_after_drill_status") != "ok":
        blockers.append("reconcile_after_drill_not_ok")
    if payload.get("live_write_allowed_during_drill") is not False:
        blockers.append("live_write_allowed_during_drill")
    if payload.get("real_exchange_order_sent") is not False:
        blockers.append("real_exchange_order_sent")
    if payload.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return ExternalSafetyDrillAssessment(status, blockers, warnings)


def simulate_safety_drill(mode: str) -> SafetyDrillEvidence:
    kill_switch_active = True
    safety_latch_active = True
    opening_blocked_ks = kill_switch_active
    opening_blocked_latch = safety_latch_active
    emergency_reduce_only = True
    emergency_safe = emergency_reduce_only and opening_blocked_ks and opening_blocked_latch
    audit_expected = True
    alert_expected = True
    go_no_go = "NO_GO" if opening_blocked_ks and opening_blocked_latch and emergency_safe else "FAIL"
    return SafetyDrillEvidence(
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha(),
        mode=mode,
        kill_switch_active=kill_switch_active,
        safety_latch_active=safety_latch_active,
        opening_order_blocked_by_kill_switch=opening_blocked_ks,
        opening_order_blocked_by_safety_latch=opening_blocked_latch,
        emergency_flatten_reduce_only=emergency_reduce_only,
        emergency_flatten_safe=emergency_safe,
        audit_expected=audit_expected,
        alert_expected=alert_expected,
        go_no_go=go_no_go,
        live_write_allowed=False,
    )


def evidence_to_markdown(evidence: SafetyDrillEvidence) -> str:
    return "\n".join(
        [
            "# Live Safety Drill Evidence",
            "",
            f"- Datum/Zeit: `{evidence.generated_at}`",
            f"- Git SHA: `{evidence.git_sha}`",
            f"- Modus: `{evidence.mode}`",
            f"- Kill-Switch aktiv: `{str(evidence.kill_switch_active).lower()}`",
            f"- Safety-Latch aktiv: `{str(evidence.safety_latch_active).lower()}`",
            f"- Opening Order blockiert: `{str(evidence.opening_order_blocked_by_kill_switch and evidence.opening_order_blocked_by_safety_latch).lower()}`",
            f"- Emergency-Flatten reduce-only: `{str(evidence.emergency_flatten_reduce_only).lower()}`",
            f"- Audit erwartet: `{str(evidence.audit_expected).lower()}`",
            f"- Alert erwartet: `{str(evidence.alert_expected).lower()}`",
            f"- Go/No-Go: `{evidence.go_no_go}`",
            f"- Live-Write erlaubt: `{str(evidence.live_write_allowed).lower()}`",
            "",
            "## Redacted JSON",
            "```json",
            json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    )


def external_evidence_to_markdown(
    payload: dict[str, Any],
    assessment: ExternalSafetyDrillAssessment,
    secret_issues: list[str],
) -> str:
    lines = [
        "# Live Safety Drill Evidence Check",
        "",
        "Status: prueft externen Kill-Switch-/Safety-Latch-/Emergency-Flatten-Nachweis ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Execution Mode: `{payload.get('execution_mode')}`",
        f"- Git SHA: `{payload.get('git_sha') or 'missing'}`",
        f"- Operator: `{payload.get('operator') or 'missing'}`",
        f"- Reconcile nach Drill: `{payload.get('reconcile_after_drill_status') or 'missing'}`",
        f"- Ergebnis: `{assessment.status}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in assessment.blockers)
    if not assessment.blockers:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in assessment.warnings)
    if not assessment.warnings:
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
            "- Simulierte Drills sind Code-Evidence, aber keine Live-Freigabe.",
            "- Live bleibt `NO_GO`, bis ein echter Staging-/Shadow-Drill mit Audit, Alert, Reconcile und Owner-Signoff vorliegt.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=("simulated",), default="simulated")
    parser.add_argument("--evidence-json", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_drill_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_template}")
        return 0
    if args.evidence_json:
        loaded = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Evidence root muss ein JSON-Objekt sein.")
        assessment = assess_external_safety_drill(loaded)
        secret_issues = secret_surface_issues(loaded)
        payload = {
            "ok": assessment.status == "PASS" and not secret_issues,
            "status": assessment.status,
            "blockers": list(assessment.blockers) + secret_issues,
            "warnings": list(assessment.warnings),
        }
        if args.output_md:
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(
                external_evidence_to_markdown(loaded, assessment, secret_issues),
                encoding="utf-8",
            )
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(external_evidence_to_markdown(loaded, assessment, secret_issues), end="")
        return 1 if args.strict and not payload["ok"] else 0
    mode = "dry-run" if args.dry_run else args.mode
    evidence = simulate_safety_drill(mode)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(evidence_to_markdown(evidence), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "live_safety_drill: "
            f"go_no_go={evidence.go_no_go} mode={evidence.mode} live_write_allowed=false"
        )
    return 0 if evidence.go_no_go == "NO_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
