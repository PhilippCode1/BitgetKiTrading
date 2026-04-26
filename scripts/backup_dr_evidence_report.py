#!/usr/bin/env python3
"""Kombinierter Backup-/Restore-/Disaster-Recovery-Evidence-Report."""

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dr_postgres_restore_test import (  # noqa: E402
    DEFAULT_EVIDENCE_TEMPLATE as RESTORE_TEMPLATE,
    assess_external_restore_evidence,
    build_restore_evidence,
    secret_surface_issues as restore_secret_surface_issues,
)
from scripts.live_safety_drill import (  # noqa: E402
    DEFAULT_DRILL_TEMPLATE as SAFETY_TEMPLATE,
    assess_external_safety_drill,
    secret_surface_issues as safety_secret_surface_issues,
    simulate_safety_drill,
)

REQUIRED_RESTORE_BLOCKERS = (
    "restore_status_not_pass",
    "rto_seconds_missing",
    "rpo_seconds_missing",
    "checksum_not_verified",
    "migration_smoke_not_passed",
    "live_broker_read_smoke_not_passed",
    "reconcile_state_not_validated",
    "audit_trail_not_restored",
    "safety_latch_default_not_blocked",
    "alert_route_not_verified",
)
REQUIRED_SAFETY_BLOCKERS = (
    "kill_switch_arm_not_verified",
    "kill_switch_opening_submit_not_blocked",
    "safety_latch_submit_not_blocked",
    "emergency_flatten_not_tested",
    "audit_trail_not_verified",
    "alert_delivery_not_verified",
    "main_console_state_not_verified",
    "reconcile_after_drill_not_ok",
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


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} muss ein JSON-Objekt enthalten.")
    return loaded


def build_report_payload() -> dict[str, Any]:
    restore_payload = _load_json(RESTORE_TEMPLATE)
    safety_payload = _load_json(SAFETY_TEMPLATE)
    restore_assessment = assess_external_restore_evidence(restore_payload)
    safety_assessment = assess_external_safety_drill(safety_payload)
    restore_secret_issues = restore_secret_surface_issues(restore_payload)
    safety_secret_issues = safety_secret_surface_issues(safety_payload)
    restore_dry_run = build_restore_evidence(database_url="", dry_run=True)
    safety_simulation = simulate_safety_drill("simulated")

    restore_missing_blockers = sorted(set(REQUIRED_RESTORE_BLOCKERS) - set(restore_assessment.blockers))
    safety_missing_blockers = sorted(set(REQUIRED_SAFETY_BLOCKERS) - set(safety_assessment.blockers))
    failures: list[str] = []
    if restore_assessment.status != "FAIL":
        failures.append("restore_template_must_fail_until_external_evidence")
    if safety_assessment.status != "FAIL":
        failures.append("safety_template_must_fail_until_external_evidence")
    if restore_secret_issues or safety_secret_issues:
        failures.append("unredacted_secret_surface_detected")
    if restore_missing_blockers:
        failures.append("restore_template_missing_required_blocker_coverage")
    if safety_missing_blockers:
        failures.append("safety_template_missing_required_blocker_coverage")
    if restore_dry_run.status != "DRY_RUN" or restore_dry_run.live_ready:
        failures.append("restore_dry_run_not_live_blocking")
    if safety_simulation.live_write_allowed:
        failures.append("safety_simulation_allows_live_write")

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "restore_template": {
            "path": str(RESTORE_TEMPLATE.relative_to(ROOT)),
            "status": restore_assessment.status,
            "blockers": restore_assessment.blockers,
            "warnings": restore_assessment.warnings,
            "secret_surface_issues": restore_secret_issues,
            "missing_required_blockers": restore_missing_blockers,
        },
        "safety_template": {
            "path": str(SAFETY_TEMPLATE.relative_to(ROOT)),
            "status": safety_assessment.status,
            "blockers": safety_assessment.blockers,
            "warnings": safety_assessment.warnings,
            "secret_surface_issues": safety_secret_issues,
            "missing_required_blockers": safety_missing_blockers,
        },
        "local_dry_runs": {
            "postgres_restore": asdict(restore_dry_run),
            "live_safety_drill": asdict(safety_simulation),
        },
        "external_required": [
            "real_staging_or_clone_postgres_restore_pass_missing",
            "rto_rpo_restore_budget_evidence_missing",
            "disaster_recovery_drill_with_reconcile_audit_alert_missing",
            "owner_signed_restore_dr_acceptance_missing",
        ],
        "failures": failures,
        "notes": [
            "Dieser Report beweist nur repo-lokale Contracts und Fail-Closed-Verhalten.",
            "Ein Template-PASS ohne externen Nachweis waere ein Fehler; die Templates muessen im Repo blockieren.",
            "Private Live bleibt verboten, bis echter Restore/DR-Drill mit Evidence-Referenz und Owner-Signoff vorliegt.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Backup / Restore / Disaster Recovery Evidence Report",
        "",
        "Status: kombinierter repo-lokaler DR-Nachweis ohne echte Secrets, ohne DB-Mutation und ohne Exchange-Write.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- External Required: `{len(payload['external_required'])}`",
        f"- Restore-Template-Status: `{payload['restore_template']['status']}`",
        f"- Safety-Template-Status: `{payload['safety_template']['status']}`",
        "",
        "## Restore-Contract",
        "",
        f"- Template: `{payload['restore_template']['path']}`",
        f"- Blocker: `{len(payload['restore_template']['blockers'])}`",
        f"- Secret-Surface-Issues: `{len(payload['restore_template']['secret_surface_issues'])}`",
        f"- Fehlende Pflichtblocker-Abdeckung: `{len(payload['restore_template']['missing_required_blockers'])}`",
        "",
        "## Safety-/DR-Contract",
        "",
        f"- Template: `{payload['safety_template']['path']}`",
        f"- Blocker: `{len(payload['safety_template']['blockers'])}`",
        f"- Secret-Surface-Issues: `{len(payload['safety_template']['secret_surface_issues'])}`",
        f"- Fehlende Pflichtblocker-Abdeckung: `{len(payload['safety_template']['missing_required_blockers'])}`",
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
        "backup_dr_evidence_report: "
        f"failures={len(payload['failures'])} "
        f"external_required={len(payload['external_required'])} "
        f"private_live={payload['private_live_decision']}"
    )
    if args.strict and payload["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
