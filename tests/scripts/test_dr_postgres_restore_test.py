from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from scripts.dr_postgres_restore_test import (
    assess_external_restore_evidence,
    build_external_restore_template,
    build_restore_evidence,
    evidence_to_markdown,
    redact_database_url,
    secret_surface_issues,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dr_postgres_restore_test.py"
TEMPLATE = ROOT / "docs" / "production_10_10" / "postgres_restore_evidence.template.json"


def test_dry_run_works() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "dry_run=true" in completed.stdout


def test_production_url_blocked() -> None:
    evidence = build_restore_evidence(
        database_url="postgresql://app:secret@prod-db.internal:5432/app",
        dry_run=False,
        acknowledged_test_db=True,
    )
    assert evidence.status == "FAIL"
    assert "Production-DB" in evidence.message


def test_password_redacted() -> None:
    redacted = redact_database_url("postgresql://user:super-secret@localhost:5432/db")
    assert "super-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_report_contains_rto_rpo() -> None:
    evidence = build_restore_evidence(database_url="", dry_run=True)
    md = evidence_to_markdown(evidence)
    assert "RTO Sekunden" in md
    assert "RPO Sekunden" in md


def _valid_external_payload() -> dict[str, object]:
    payload = build_external_restore_template()
    payload.update(
        {
            "backup_label": "hourly-staging-20260426-0000",
            "backup_storage_encrypted": True,
            "backup_artifact_sha256": "a" * 64,
            "restore_status": "PASS",
            "restore_target": "staging-clone-db",
            "git_sha": "84d7b66",
            "rto_seconds": 120,
            "rto_budget_seconds": 600,
            "rpo_seconds": 60,
            "rpo_budget_seconds": 300,
            "checksum_verified": True,
            "migration_smoke_passed": True,
            "live_broker_read_smoke_passed": True,
            "reconcile_state_validated": True,
            "audit_trail_restored": True,
            "safety_latch_default_blocked": True,
            "alert_route_verified": True,
            "reviewed_by": "sre-review",
            "reviewed_at": "2026-04-26T00:00:00Z",
            "evidence_reference": "external-ticket-restore-123",
            "owner_signoff": True,
        }
    )
    return payload


def test_external_restore_template_blocks_live() -> None:
    assessment = assess_external_restore_evidence(build_external_restore_template())
    assert assessment.status == "FAIL"
    assert "restore_status_not_pass" in assessment.blockers
    assert "rto_seconds_missing" in assessment.blockers
    assert "owner_signoff_missing_external_required" in assessment.warnings


def test_valid_external_restore_evidence_passes_contract() -> None:
    assessment = assess_external_restore_evidence(_valid_external_payload())
    assert assessment.status == "PASS"
    assert assessment.blockers == []
    assert assessment.warnings == []


def test_external_restore_evidence_blocks_budget_exceeded() -> None:
    payload = _valid_external_payload()
    payload["rto_seconds"] = 700
    assessment = assess_external_restore_evidence(payload)
    assert assessment.status == "FAIL"
    assert "rto_budget_exceeded" in assessment.blockers


def test_external_restore_secret_surface_blocks_unredacted_values() -> None:
    assert secret_surface_issues({"database_url": "postgresql://u:secret@host/db"}) == [
        "secret_like_field_not_redacted:database_url"
    ]
    assert secret_surface_issues({"database_url": "[REDACTED]", "dsn": "not_stored_in_repo"}) == []


def test_cli_template_strict_fails_and_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--evidence-json", str(TEMPLATE), "--strict", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert "restore_status_not_pass" in payload["blockers"]


def test_cli_writes_output_json_for_dry_run(tmp_path: Path) -> None:
    out_json = tmp_path / "restore.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dry-run",
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "DRY_RUN"
    assert payload["live_ready"] is False
