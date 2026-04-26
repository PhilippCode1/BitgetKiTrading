from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from scripts.reconcile_truth_drill import (
    assess_external_evidence,
    build_external_evidence_template,
    secret_surface_issues,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reconcile_truth_drill.py"
TEMPLATE = ROOT / "docs" / "production_10_10" / "reconcile_idempotency_evidence.template.json"


def test_drill_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run ok" in completed.stdout


def test_drill_report_contains_scenarios_and_no_secrets(tmp_path: Path) -> None:
    out = tmp_path / "drill.md"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "simulated", "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    text = out.read_text(encoding="utf-8")
    assert "exchange_order_missing" in text
    assert "local_order_missing" in text
    assert "position_mismatch" in text
    assert "unknown_order_state" in text
    assert "safety_latch_required" in text
    lowered = text.lower()
    assert "secret" not in lowered
    assert "token" not in lowered
    assert "password" not in lowered


def _valid_external_evidence() -> dict[str, object]:
    payload = build_external_evidence_template()
    payload.update(
        {
            "drill_started_at": "2026-04-26T00:00:00Z",
            "drill_completed_at": "2026-04-26T00:15:00Z",
            "git_sha": "84d7b66",
            "operator": "ops-review",
            "evidence_reference": "external-reconcile-idempotency-123",
            "exchange_truth_source": "bitget-readonly-staging",
            "reconcile_status": "ok",
            "reconcile_snapshot_fresh": True,
            "per_asset_reconcile_ok": {"BTCUSDT": True, "ETHUSDT": True},
            "open_drift_count": 0,
            "unknown_order_state_count": 0,
            "position_mismatch_count": 0,
            "fill_mismatch_count": 0,
            "missing_exchange_ack_count": 0,
            "retry_without_reconcile_blocked": True,
            "duplicate_client_oid_blocked": True,
            "idempotency_key_required": True,
            "timeout_sets_unknown_submit_state": True,
            "unknown_submit_state_blocks_opening": True,
            "db_failure_after_submit_requires_reconcile": True,
            "safety_latch_armed_on_unresolved_duplicate": True,
            "audit_trail_verified": True,
            "alert_delivery_verified": True,
            "main_console_reconcile_state_verified": True,
            "owner_signoff": True,
        }
    )
    return payload


def test_external_template_blocks_live() -> None:
    status, blockers, warnings = assess_external_evidence(build_external_evidence_template())
    assert status == "FAIL"
    assert "reconcile_status_not_ok" in blockers
    assert "per_asset_reconcile_missing" in blockers
    assert "duplicate_client_oid_not_blocked" in blockers
    assert "owner_signoff_missing_external_required" in warnings


def test_valid_external_evidence_passes_contract() -> None:
    status, blockers, warnings = assess_external_evidence(_valid_external_evidence())
    assert status == "PASS"
    assert blockers == []
    assert warnings == []


def test_external_evidence_blocks_real_exchange_order() -> None:
    payload = _valid_external_evidence()
    payload["real_exchange_order_sent"] = True
    status, blockers, _warnings = assess_external_evidence(payload)
    assert status == "FAIL"
    assert "real_exchange_order_sent" in blockers


def test_external_secret_surface_blocks_unredacted_values() -> None:
    assert secret_surface_issues({"authorization": "Bearer real-token"}) == [
        "secret_like_field_not_redacted:authorization"
    ]
    assert secret_surface_issues({"authorization": "[REDACTED]", "database_url": "not_stored_in_repo"}) == []


def test_cli_template_strict_fails_and_writes_json(tmp_path: Path) -> None:
    out_json = tmp_path / "reconcile.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--evidence-json",
            str(TEMPLATE),
            "--strict",
            "--output-md",
            str(tmp_path / "reconcile.md"),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "reconcile_status_not_ok" in payload["blockers"]
    assert "idempotency_key_not_required" in payload["blockers"]
