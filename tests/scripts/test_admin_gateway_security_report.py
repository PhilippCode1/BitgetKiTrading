from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.admin_gateway_security_report import build_report_payload

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "admin_gateway_security_report.py"


def test_payload_covers_required_security_scenarios() -> None:
    payload = build_report_payload()
    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert payload["missing_required_scenarios"] == []
    assert payload["failures"] == []
    assert payload["secret_safe"] is True
    assert payload["audit_valid_count"] == payload["scenario_count"]


def test_owner_admin_and_gateway_mutation_rules_are_visible() -> None:
    payload = build_report_payload()
    by_id = {row["id"]: row for row in payload["scenarios"]}
    assert by_id["missing_auth_blocks_admin"]["blocks_sensitive_action"] is True
    assert by_id["single_admin_subject_mismatch_blocks"]["blocks_sensitive_action"] is True
    assert by_id["legacy_admin_token_forbidden_in_production"]["blocks_sensitive_action"] is True
    assert by_id["read_role_cannot_mutate_live_broker"]["blocks_sensitive_action"] is True
    assert by_id["customer_portal_cannot_admin"]["blocks_sensitive_action"] is True
    assert by_id["public_secret_env_blocked"]["blocks_sensitive_action"] is True
    assert by_id["operator_role_requires_manual_action_for_release"]["manual_action_required"] is True
    assert by_id["emergency_role_requires_manual_action_for_flatten"]["manual_action_required"] is True
    assert by_id["auth_errors_are_redacted"]["secret_safe"] is True


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "admin_gateway_security.md"
    out_json = tmp_path / "admin_gateway_security.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "admin_gateway_security_report" in completed.stdout
    assert "# Admin / API-Gateway Security Evidence Report" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 9
    assert payload["missing_required_scenarios"] == []
    assert payload["failures"] == []
