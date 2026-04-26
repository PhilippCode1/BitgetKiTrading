#!/usr/bin/env python3
"""Safe Postgres restore evidence adapter for private live approval."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESTORE_EVIDENCE_SCHEMA_VERSION = "postgres-restore-dr-evidence-v1"
DEFAULT_EVIDENCE_TEMPLATE = ROOT / "docs" / "production_10_10" / "postgres_restore_evidence.template.json"
SECRET_LIKE_KEYS = ("database_url", "dsn", "password", "secret", "token", "api_key", "private_key")


@dataclass(frozen=True)
class RestoreEvidence:
    status: str
    generated_at: str
    git_sha: str
    dry_run: bool
    database_url_redacted: str
    rto_seconds: float | None
    rpo_seconds: float | None
    live_ready: bool
    message: str


@dataclass(frozen=True)
class ExternalRestoreEvidenceAssessment:
    status: str
    blockers: list[str]
    warnings: list[str]


def redact_database_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"(?i)([a-z0-9+]+://[^:/@\s]+:)([^@\s]+)(@)", r"\1[REDACTED]\3", url)


def is_production_database_url(url: str) -> bool:
    lowered = url.lower()
    production_markers = ("prod", "production", "rds.amazonaws.com", "azure.com", "cloudsql")
    test_markers = ("test", "staging", "shadow", "local", "localhost", "127.0.0.1")
    return any(marker in lowered for marker in production_markers) and not any(
        marker in lowered for marker in test_markers
    )


def build_external_restore_template() -> dict[str, Any]:
    return {
        "schema_version": RESTORE_EVIDENCE_SCHEMA_VERSION,
        "environment": "staging",
        "backup_label": "",
        "backup_storage_encrypted": False,
        "backup_artifact_sha256": "",
        "restore_status": "PENDING",
        "restore_target": "",
        "git_sha": "",
        "rto_seconds": None,
        "rto_budget_seconds": 600,
        "rpo_seconds": None,
        "rpo_budget_seconds": 300,
        "checksum_verified": False,
        "migration_smoke_passed": False,
        "live_broker_read_smoke_passed": False,
        "reconcile_state_validated": False,
        "audit_trail_restored": False,
        "safety_latch_default_blocked": False,
        "alert_route_verified": False,
        "reviewed_by": "",
        "reviewed_at": "",
        "evidence_reference": "",
        "owner_signoff": False,
        "database_url": "[REDACTED]",
        "notes_de": "Template: echten Restore gegen Staging-/Clone-DB extern ausfuehren; Secrets niemals im Repo speichern.",
    }


def _positive_number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def secret_surface_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def assess_external_restore_evidence(payload: dict[str, Any] | None) -> ExternalRestoreEvidenceAssessment:
    if not payload:
        return ExternalRestoreEvidenceAssessment("FAIL", ["restore_evidence_missing"], [])
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != RESTORE_EVIDENCE_SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if payload.get("environment") not in {"staging", "production_clone", "shadow_clone"}:
        blockers.append("environment_invalid")
    if not str(payload.get("backup_label") or "").strip():
        blockers.append("backup_label_missing")
    if payload.get("backup_storage_encrypted") is not True:
        blockers.append("backup_storage_encryption_not_confirmed")
    if not str(payload.get("backup_artifact_sha256") or "").strip():
        blockers.append("backup_artifact_sha256_missing")
    if payload.get("restore_status") != "PASS":
        blockers.append("restore_status_not_pass")
    if not str(payload.get("restore_target") or "").strip():
        blockers.append("restore_target_missing")
    if not str(payload.get("git_sha") or "").strip():
        blockers.append("git_sha_missing")

    rto = _positive_number(payload, "rto_seconds")
    rto_budget = _positive_number(payload, "rto_budget_seconds")
    rpo = _positive_number(payload, "rpo_seconds")
    rpo_budget = _positive_number(payload, "rpo_budget_seconds")
    if rto is None:
        blockers.append("rto_seconds_missing")
    if rto_budget is None:
        blockers.append("rto_budget_seconds_missing")
    if rto is not None and rto_budget is not None and rto > rto_budget:
        blockers.append("rto_budget_exceeded")
    if rpo is None:
        blockers.append("rpo_seconds_missing")
    if rpo_budget is None:
        blockers.append("rpo_budget_seconds_missing")
    if rpo is not None and rpo_budget is not None and rpo > rpo_budget:
        blockers.append("rpo_budget_exceeded")

    required_true = (
        ("checksum_verified", "checksum_not_verified"),
        ("migration_smoke_passed", "migration_smoke_not_passed"),
        ("live_broker_read_smoke_passed", "live_broker_read_smoke_not_passed"),
        ("reconcile_state_validated", "reconcile_state_not_validated"),
        ("audit_trail_restored", "audit_trail_not_restored"),
        ("safety_latch_default_blocked", "safety_latch_default_not_blocked"),
        ("alert_route_verified", "alert_route_not_verified"),
    )
    for key, code in required_true:
        if payload.get(key) is not True:
            blockers.append(code)

    if not str(payload.get("reviewed_by") or "").strip():
        blockers.append("reviewer_missing")
    if not str(payload.get("reviewed_at") or "").strip():
        blockers.append("reviewed_at_missing")
    if not str(payload.get("evidence_reference") or "").strip():
        blockers.append("evidence_reference_missing")
    if payload.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return ExternalRestoreEvidenceAssessment(status, blockers, warnings)


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


def build_restore_evidence(
    *,
    database_url: str = "",
    dry_run: bool,
    acknowledged_test_db: bool = False,
) -> RestoreEvidence:
    if database_url and is_production_database_url(database_url):
        return RestoreEvidence(
            status="FAIL",
            generated_at=datetime.now(tz=UTC).isoformat(),
            git_sha=git_sha(),
            dry_run=dry_run,
            database_url_redacted=redact_database_url(database_url),
            rto_seconds=None,
            rpo_seconds=None,
            live_ready=False,
            message="Production-DB wird fuer Restore-Test blockiert.",
        )
    if not dry_run and not acknowledged_test_db:
        return RestoreEvidence(
            status="FAIL",
            generated_at=datetime.now(tz=UTC).isoformat(),
            git_sha=git_sha(),
            dry_run=False,
            database_url_redacted=redact_database_url(database_url),
            rto_seconds=None,
            rpo_seconds=None,
            live_ready=False,
            message="Nicht-dry-run verlangt --i-understand-this-is-a-test-db.",
        )
    return RestoreEvidence(
        status="DRY_RUN" if dry_run else "EXTERNAL_REQUIRED",
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha(),
        dry_run=dry_run,
        database_url_redacted=redact_database_url(database_url),
        rto_seconds=0.0 if dry_run else None,
        rpo_seconds=0.0 if dry_run else None,
        live_ready=False,
        message=(
            "Dry-run: keine DB-Mutation. Echter Restore-Report mit RTO/RPO bleibt Pflicht."
            if dry_run
            else "Test-DB bestaetigt; echter Restore-Run muss extern ausgefuehrt und archiviert werden."
        ),
    )


def evidence_to_markdown(evidence: RestoreEvidence) -> str:
    payload = asdict(evidence)
    return "\n".join(
        [
            "# Postgres Restore Test Evidence",
            "",
            f"- Datum/Zeit: `{evidence.generated_at}`",
            f"- Git SHA: `{evidence.git_sha}`",
            f"- Status: `{evidence.status}`",
            f"- Dry-run: `{str(evidence.dry_run).lower()}`",
            f"- Database URL: `{evidence.database_url_redacted or 'nicht gesetzt'}`",
            f"- RTO Sekunden: `{evidence.rto_seconds}`",
            f"- RPO Sekunden: `{evidence.rpo_seconds}`",
            f"- Live-ready: `{str(evidence.live_ready).lower()}`",
            f"- Aussage: {evidence.message}",
            "",
            "## Redacted JSON",
            "```json",
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    )


def external_evidence_to_markdown(
    payload: dict[str, Any],
    assessment: ExternalRestoreEvidenceAssessment,
    secret_issues: list[str],
) -> str:
    lines = [
        "# Postgres Restore / Disaster Recovery Evidence Check",
        "",
        "Status: prueft externen Restore-/DR-Nachweis ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Backup Label: `{payload.get('backup_label') or 'missing'}`",
        f"- Restore Status: `{payload.get('restore_status')}`",
        f"- Git SHA: `{payload.get('git_sha') or 'missing'}`",
        f"- RTO Sekunden: `{payload.get('rto_seconds')}` / Budget `{payload.get('rto_budget_seconds')}`",
        f"- RPO Sekunden: `{payload.get('rpo_seconds')}` / Budget `{payload.get('rpo_budget_seconds')}`",
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
            "- Nur ein echter Staging-/Clone-Restore mit PASS, RTO/RPO und Review kann Live-Evidence sein.",
            "- Dry-run, Template oder fehlende externe Referenz bleiben `NO_GO` fuer Live.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--evidence-json", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--i-understand-this-is-a-test-db", action="store_true")
    args = parser.parse_args(argv)
    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_restore_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_template}")
        return 0
    if args.evidence_json:
        loaded = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Evidence root muss ein JSON-Objekt sein.")
        assessment = assess_external_restore_evidence(loaded)
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
            args.output_json.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
                encoding="utf-8",
            )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(
                "dr_postgres_restore_test: "
                f"external_status={assessment.status} blockers={len(payload['blockers'])} "
                f"warnings={len(payload['warnings'])}"
            )
            for blocker in payload["blockers"]:
                print(f"BLOCKER {blocker}")
            for warning in payload["warnings"]:
                print(f"WARNING {warning}")
        return 1 if args.strict and not payload["ok"] else 0
    evidence = build_restore_evidence(
        database_url=args.database_url,
        dry_run=args.dry_run,
        acknowledged_test_db=args.i_understand_this_is_a_test_db,
    )
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
            f"dr_postgres_restore_test: status={evidence.status} "
            f"dry_run={str(evidence.dry_run).lower()} live_ready=false"
        )
        print(evidence.message)
    return 1 if evidence.status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
