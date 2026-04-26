from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.branch_protection_ci_evidence_report import (
    assess_external_template,
    build_report_payload,
)

REPO = Path(__file__).resolve().parents[2]


def _verified_external_dict() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "synthetic.reviewer",
        "reviewed_at": "2026-01-01T00:00:00Z",
        "git_host": "github",
        "repository": "synthetic-owner/synthetic-repo",
        "default_branch": "main",
        "github_settings": {
            "required_status_checks_include_release_approval_gate": True,
            "required_pull_request_reviews_min_1": True,
            "no_force_push": True,
            "no_branch_deletion": True,
            "admin_enforce_or_documented_exception": True,
        },
        "artifacts": {
            "settings_export_or_screenshot_uri": "https://example.invalid/screenshot-redacted.png",
            "ci_workflow_run_green_reference": "https://example.invalid/actions/run/1",
        },
        "safety": {
            "no_secrets_in_export": True,
            "owner_signoff": True,
        },
    }


def test_default_payload_no_internal_issues_and_blocks_private_live() -> None:
    p = build_report_payload()
    assert p["internal_issues"] == []
    assert p["private_live_decision"] == "NO_GO"
    assert p["full_autonomous_live"] == "NO_GO"
    assert p["external_template_assessment"]["status"] == "FAIL"
    assert p["ci_workflow_mandatory_jobs"]["ok"] is True


def test_assess_external_template_passes_for_synthetic_verified() -> None:
    r = assess_external_template(_verified_external_dict())
    assert r["status"] == "PASS"
    assert not r["failures"]


def test_assess_external_template_fails_for_template_status() -> None:
    load = json.loads(
        (REPO / "docs" / "production_10_10" / "branch_protection_evidence.template.json").read_text(
            encoding="utf-8"
        )
    )
    r = assess_external_template(load)
    assert r["status"] == "FAIL"
    assert "status" in r["failures"]


def test_cli_strict_succeeds_without_token(tmp_path: Path) -> None:
    out_md = tmp_path / "bp.md"
    out_json = tmp_path / "bp.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "branch_protection_ci_evidence_report.py"),
            "--strict",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["internal_issues"] == []


def test_cli_strict_external_fails_with_repo_template() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "branch_protection_ci_evidence_report.py"),
            "--strict",
            "--strict-external",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1


def test_cli_strict_external_passes_with_synthetic_verified_json(tmp_path: Path) -> None:
    ext = tmp_path / "verified.json"
    ext.write_text(json.dumps(_verified_external_dict(), indent=2), encoding="utf-8")
    out_json = tmp_path / "out.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "branch_protection_ci_evidence_report.py"),
            "--strict",
            "--strict-external",
            "--external-json",
            str(ext),
            "--output-json",
            str(out_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["external_template_assessment"]["status"] == "PASS"
