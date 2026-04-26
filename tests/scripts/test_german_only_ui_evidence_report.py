from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.german_only_ui_evidence_report import (
    assess_uat_evidence,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "german_only_ui_evidence_report.py"
UAT_DEFAULT = ROOT / "docs" / "production_10_10" / "german_only_ui_uat.template.json"


def _verified_uat() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "owner",
        "reviewed_at": "2026-04-26T12:00:00Z",
        "environment": "local",
        "git_sha": "abc",
        "main_console": {
            "all_visible_labels_german_or_documented": True,
            "no_english_marketing_phrases_in_operator_flow": True,
            "legacy_commerce_routes_acknowledged": True,
        },
        "spot_checks": {
            "navigation_matches_policy": True,
            "safety_states_readable_de": True,
            "error_messages_not_english_only": True,
        },
        "safety": {
            "no_secrets_in_screenshots": True,
            "owner_signoff": True,
        },
    }


def test_default_payload_no_internal_blockers() -> None:
    payload = build_report_payload(uat_json=UAT_DEFAULT)
    assert not payload["internal_issues"]
    assert payload["german_only_scan"]["ok"] is True
    assert payload["german_ui_language"]["ok"] is True
    assert payload["owner_uat_assessment"]["status"] == "FAIL"


def test_uat_assess_pass() -> None:
    a = assess_uat_evidence(_verified_uat())
    assert a["status"] == "PASS"
    assert not a["failures"]


def test_cli(tmp_path: Path) -> None:
    u = tmp_path / "uat.json"
    u.write_text(json.dumps(_verified_uat(), indent=2), encoding="utf-8")
    r0 = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r0.returncode == 0, r0.stderr
    r1 = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict", "--strict-external"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 1
    r2 = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict", "--strict-external", f"--uat-json={u}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stderr
