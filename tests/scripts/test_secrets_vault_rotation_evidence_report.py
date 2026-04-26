from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.secrets_vault_rotation_evidence_report import (
    REQUIRED_CRITICAL_POLICIES,
    build_report_payload,
)

REPO = Path(__file__).resolve().parents[2]


def test_payload_blocks_private_live_until_external_secret_evidence_exists() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert "vault_runtime_secret_store_attestation_missing" in payload["external_required"]
    assert "real_secret_rotation_drill_missing" in payload["external_required"]
    assert "owner_signed_secret_rotation_acceptance_missing" in payload["external_required"]


def test_payload_has_no_browser_secret_leaks_and_no_template_failures() -> None:
    payload = build_report_payload()

    assert payload["failures"] == []
    assert payload["secret_surface"]["browser_public_leak_count"] == 0
    assert all(item["ok"] for item in payload["templates"])


def test_payload_covers_critical_rotation_policies() -> None:
    payload = build_report_payload()
    rotation = payload["rotation_policy"]

    assert rotation["required_policy_missing"] == []
    assert set(REQUIRED_CRITICAL_POLICIES).issubset(set(rotation["reuse_forbidden_critical"]))
    assert all(item["expired"] is True for item in rotation["stale_examples"])
    assert payload["simulated_rotation_drill"]["raw_secret_values_included"] is False


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "secrets.md"
    output_json = tmp_path / "secrets.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "secrets_vault_rotation_evidence_report.py"),
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
    assert payload["private_live_decision"] == "NO_GO"
