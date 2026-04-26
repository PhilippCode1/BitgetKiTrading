from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from scripts.live_safety_drill import (
    assess_external_safety_drill,
    build_external_drill_template,
    evidence_to_markdown,
    secret_surface_issues,
    simulate_safety_drill,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "live_safety_drill.py"
TEMPLATE = ROOT / "docs" / "production_10_10" / "live_safety_drill.template.json"


def test_kill_switch_blocks_opening() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.kill_switch_active is True
    assert evidence.opening_order_blocked_by_kill_switch is True


def test_safety_latch_blocks_opening() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.safety_latch_active is True
    assert evidence.opening_order_blocked_by_safety_latch is True


def test_emergency_flatten_is_safe_reduce_only() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.emergency_flatten_reduce_only is True
    assert evidence.emergency_flatten_safe is True


def test_report_contains_go_no_go(tmp_path: Path) -> None:
    report = tmp_path / "live_safety_drill.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "simulated", "--output-md", str(report)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    text = report.read_text(encoding="utf-8")
    assert "Go/No-Go" in text
    assert "NO_GO" in text
    assert "Live-Write erlaubt" in text
    assert "live_write_allowed" in evidence_to_markdown(simulate_safety_drill("simulated"))


def _valid_external_drill() -> dict[str, object]:
    payload = build_external_drill_template()
    payload.update(
        {
            "drill_started_at": "2026-04-26T00:00:00Z",
            "drill_completed_at": "2026-04-26T00:15:00Z",
            "git_sha": "84d7b66",
            "operator": "ops-review",
            "evidence_reference": "external-safety-drill-123",
            "kill_switch_arm_verified": True,
            "kill_switch_blocks_opening_submit": True,
            "kill_switch_release_requires_operator": True,
            "safety_latch_arm_verified": True,
            "safety_latch_blocks_submit": True,
            "safety_latch_blocks_replace": True,
            "safety_latch_release_requires_reason": True,
            "emergency_flatten_tested": True,
            "emergency_flatten_reduce_only": True,
            "emergency_flatten_exchange_truth_checked": True,
            "emergency_flatten_no_increase_only": True,
            "cancel_all_tested": True,
            "audit_trail_verified": True,
            "alert_delivery_verified": True,
            "main_console_state_verified": True,
            "reconcile_after_drill_status": "ok",
            "owner_signoff": True,
        }
    )
    return payload


def test_external_safety_template_blocks_live() -> None:
    assessment = assess_external_safety_drill(build_external_drill_template())
    assert assessment.status == "FAIL"
    assert "kill_switch_arm_not_verified" in assessment.blockers
    assert "safety_latch_submit_not_blocked" in assessment.blockers
    assert "emergency_flatten_not_reduce_only" in assessment.blockers
    assert "owner_signoff_missing_external_required" in assessment.warnings


def test_valid_external_safety_drill_passes_contract() -> None:
    assessment = assess_external_safety_drill(_valid_external_drill())
    assert assessment.status == "PASS"
    assert assessment.blockers == []
    assert assessment.warnings == []


def test_external_safety_drill_blocks_real_exchange_order() -> None:
    payload = _valid_external_drill()
    payload["real_exchange_order_sent"] = True
    assessment = assess_external_safety_drill(payload)
    assert assessment.status == "FAIL"
    assert "real_exchange_order_sent" in assessment.blockers


def test_external_safety_secret_surface_blocks_unredacted_values() -> None:
    assert secret_surface_issues({"authorization": "Bearer real-token"}) == [
        "secret_like_field_not_redacted:authorization"
    ]
    assert secret_surface_issues({"authorization": "[REDACTED]", "database_url": "not_stored_in_repo"}) == []


def test_cli_template_strict_fails_and_writes_json(tmp_path: Path) -> None:
    out_json = tmp_path / "safety_drill.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--evidence-json",
            str(TEMPLATE),
            "--strict",
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
    assert "kill_switch_arm_not_verified" in payload["blockers"]
    assert "emergency_flatten_not_tested" in payload["blockers"]
