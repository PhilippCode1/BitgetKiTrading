from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.backup_dr_evidence_report import (
    REQUIRED_RESTORE_BLOCKERS,
    REQUIRED_SAFETY_BLOCKERS,
    build_report_payload,
)

REPO = Path(__file__).resolve().parents[2]


def test_payload_keeps_private_live_no_go_until_external_restore_dr_exists() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert "real_staging_or_clone_postgres_restore_pass_missing" in payload["external_required"]
    assert "disaster_recovery_drill_with_reconcile_audit_alert_missing" in payload["external_required"]
    assert "owner_signed_restore_dr_acceptance_missing" in payload["external_required"]


def test_templates_must_fail_closed_and_cover_required_blockers() -> None:
    payload = build_report_payload()

    assert payload["failures"] == []
    assert payload["restore_template"]["status"] == "FAIL"
    assert payload["safety_template"]["status"] == "FAIL"
    assert set(REQUIRED_RESTORE_BLOCKERS).issubset(set(payload["restore_template"]["blockers"]))
    assert set(REQUIRED_SAFETY_BLOCKERS).issubset(set(payload["safety_template"]["blockers"]))
    assert payload["restore_template"]["missing_required_blockers"] == []
    assert payload["safety_template"]["missing_required_blockers"] == []


def test_payload_is_secret_safe_and_local_dry_runs_do_not_unlock_live() -> None:
    payload = build_report_payload()

    assert payload["restore_template"]["secret_surface_issues"] == []
    assert payload["safety_template"]["secret_surface_issues"] == []
    assert payload["local_dry_runs"]["postgres_restore"]["status"] == "DRY_RUN"
    assert payload["local_dry_runs"]["postgres_restore"]["live_ready"] is False
    assert payload["local_dry_runs"]["live_safety_drill"]["live_write_allowed"] is False


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "backup_dr.md"
    output_json = tmp_path / "backup_dr.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "backup_dr_evidence_report.py"),
            "--strict",
            "--output-md",
            str(output_md),
            "--output-json",
            str(output_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert output_md.is_file()
    assert output_json.is_file()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["failures"] == []
    assert payload["private_live_decision"] == "NO_GO"
