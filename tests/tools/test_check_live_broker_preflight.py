from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_live_broker_preflight.py"
sys.path.insert(0, str(ROOT / "tools"))
import check_live_broker_preflight as checker  # noqa: E402


def test_checker_runs_strict() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "check_live_broker_preflight" in completed.stdout
    assert "submit_guard_missing" not in completed.stdout


def test_checker_json_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert "ok" in payload
    assert "error_count" in payload
    assert payload["scenario_count"] >= 24
    assert "asset_not_in_catalog" in payload["covered_blocking_reasons"]
    assert "liquidity_not_pass" in payload["covered_blocking_reasons"]
    assert "orderbook_missing" in payload["covered_blocking_reasons"]
    assert "market_order_slippage_gate_missing" in payload["covered_blocking_reasons"]


def test_checker_writes_preflight_matrix_report(tmp_path: Path) -> None:
    report = tmp_path / "live_broker_preflight_matrix.md"
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--write-report", str(report)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    content = report.read_text(encoding="utf-8")
    assert "# Live-Broker Preflight Matrix" in content
    assert "asset_not_in_catalog" in content
    assert "Kontrollfall" in content or "all_green_control" in content


def _valid_external_evidence() -> dict[str, object]:
    payload = checker.build_external_evidence_template()
    payload.update(
        {
            "drill_started_at": "2026-04-25T21:00:00Z",
            "drill_completed_at": "2026-04-25T21:20:00Z",
            "git_sha": "abc1234",
            "operator": "Philipp Crljic",
            "evidence_reference": "external-ticket-123",
            "preflight_matrix_passed": True,
            "all_required_blocking_reasons_covered": True,
            "provider_error_blocks_submit": True,
            "redis_missing_blocks_live": True,
            "database_missing_blocks_live": True,
            "exchange_truth_missing_blocks_submit": True,
            "public_api_timeout_blocks_submit": True,
            "private_api_timeout_blocks_submit": True,
            "stale_market_data_blocks_submit": True,
            "unknown_instrument_blocks_submit": True,
            "risk_context_missing_blocks_submit": True,
            "operator_release_missing_blocks_submit": True,
            "shadow_match_missing_blocks_submit": True,
            "reconcile_fail_blocks_submit": True,
            "kill_switch_blocks_submit": True,
            "safety_latch_blocks_submit": True,
            "idempotency_missing_blocks_submit": True,
            "audit_context_missing_blocks_submit": True,
            "warning_defaults_block_live": True,
            "all_green_control_no_exchange_submit": True,
            "audit_trail_verified": True,
            "alert_delivery_verified": True,
            "main_console_gate_state_verified": True,
            "owner_signoff": True,
        }
    )
    return payload


def test_external_template_blocks_live() -> None:
    status, blockers, warnings = checker.assess_external_evidence(checker.build_external_evidence_template())
    assert status == "FAIL"
    assert "provider_error_not_blocking" in blockers
    assert "redis_missing_not_blocking" in blockers
    assert "exchange_truth_missing_not_blocking" in blockers
    assert "owner_signoff_missing_external_required" in warnings


def test_valid_external_evidence_passes_contract() -> None:
    status, blockers, warnings = checker.assess_external_evidence(_valid_external_evidence())
    assert status == "PASS"
    assert blockers == []
    assert warnings == []


def test_external_evidence_blocks_live_writes_and_real_orders() -> None:
    payload = _valid_external_evidence()
    payload["live_write_allowed_during_drill"] = True
    payload["real_exchange_order_sent"] = True
    status, blockers, _warnings = checker.assess_external_evidence(payload)
    assert status == "FAIL"
    assert "live_write_allowed_during_drill" in blockers
    assert "real_exchange_order_sent" in blockers


def test_external_evidence_secret_surface_blocks_unredacted_values() -> None:
    payload = _valid_external_evidence()
    payload["database_url"] = "postgres://user:password@example/db"
    assert checker.secret_surface_issues(payload) == ["secret_like_field_not_redacted:database_url"]


def test_cli_external_template_strict_fails_and_writes_json(tmp_path: Path) -> None:
    evidence = tmp_path / "live_broker_fail_closed_evidence.json"
    output_json = tmp_path / "live_broker_fail_closed_evidence.result.json"
    report = tmp_path / "live_broker_fail_closed_evidence.md"
    evidence.write_text(
        json.dumps(checker.build_external_evidence_template()),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--evidence-json",
            str(evidence),
            "--strict",
            "--write-report",
            str(report),
            "--output-json",
            str(output_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(output_json.read_text(encoding="utf-8"))
    assert result["ok"] is False
    assert "provider_error_not_blocking" in result["blockers"]
    assert "# Live-Broker Fail-Closed Evidence Check" in report.read_text(encoding="utf-8")
