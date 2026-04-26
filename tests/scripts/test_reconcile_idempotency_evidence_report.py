from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.reconcile_idempotency_evidence_report import (
    REQUIRED_EXTERNAL_BLOCKERS,
    build_report_payload,
)
from scripts.risk_execution_evidence_report import REQUIRED_LIVE_PREFLIGHT_REASONS

REPO = Path(__file__).resolve().parents[2]


def test_payload_keeps_private_live_no_go_until_external_evidence_exists() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert "real_exchange_truth_reconcile_drill_missing" in payload["external_required"]
    assert "staging_duplicate_client_oid_drill_missing" in payload["external_required"]
    assert "owner_signed_reconcile_idempotency_acceptance_missing" in payload["external_required"]


def test_external_template_must_fail_closed_and_cover_required_blockers() -> None:
    payload = build_report_payload()

    assert payload["failures"] == []
    assert payload["external_template"]["status"] == "FAIL"
    assert set(REQUIRED_EXTERNAL_BLOCKERS).issubset(set(payload["external_template"]["blockers"]))
    assert payload["external_template"]["missing_required_blockers"] == []
    assert payload["external_template"]["secret_surface_issues"] == []


def test_risk_execution_covers_required_live_preflight_reasons() -> None:
    payload = build_report_payload()
    risk = payload["risk_execution"]

    assert set(REQUIRED_LIVE_PREFLIGHT_REASONS).issubset(
        set(risk["covered_live_preflight_reasons"])
    )
    assert risk["missing_required_live_preflight_reasons"] == []
    assert risk["private_live_decision"] == "NO_GO"


def test_order_and_reconcile_scenarios_are_live_blocking() -> None:
    payload = build_report_payload()

    assert payload["order_idempotency_assertions"]["missing_assertions"] == []
    assert payload["reconcile_assertions"]["missing_assertions"] == []
    assert payload["order_idempotency_assertions"]["scenario_count"] >= payload[
        "order_idempotency_assertions"
    ]["expected_count"]
    assert payload["reconcile_assertions"]["scenario_count"] >= payload[
        "reconcile_assertions"
    ]["expected_count"]


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "reconcile_idempotency.md"
    output_json = tmp_path / "reconcile_idempotency.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "reconcile_idempotency_evidence_report.py"),
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
