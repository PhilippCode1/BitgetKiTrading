from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from scripts.verify_shadow_burn_in import (
    _fixture_verdict,
    assess_shadow_certificate,
    build_shadow_certificate_template,
    certificate_secret_surface_issues,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_shadow_burn_in.py"
TEMPLATE = ROOT / "docs" / "production_10_10" / "shadow_burn_in_certificate.template.json"


def test_less_than_72h_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 12})
    assert verdict == "FAIL"
    assert "burn_in_less_than_72h" in blockers


def test_p0_incident_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 72, "p0_incidents": 1})
    assert verdict == "FAIL"
    assert "p0_incident_present" in blockers


def test_reconcile_fail_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 72, "reconcile_failures": 1})
    assert verdict == "FAIL"
    assert "reconcile_failures_present" in blockers


def test_good_fixture_passes() -> None:
    verdict, blockers, warnings = _fixture_verdict(
        {
            "hours_observed": 72,
            "multi_asset_data_quality_failures": 0,
            "reconcile_failures": 0,
            "p0_incidents": 0,
            "unexplained_no_trade_reasons": 0,
        }
    )
    assert verdict == "PASS"
    assert blockers == []
    assert warnings == []


def test_report_contains_required_fields(tmp_path: Path) -> None:
    report = tmp_path / "shadow_burn_in.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            "tests/fixtures/shadow_burn_in_sample.json",
            "--output-md",
            str(report),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    text = report.read_text(encoding="utf-8")
    assert "Shadow Burn-in Evidence" in text
    assert "Multi-Asset-Datenqualitaet" in text
    assert "Reconcile Failures" in text
    assert "P0 Incidents" in text


def _valid_certificate() -> dict[str, object]:
    payload = build_shadow_certificate_template()
    payload.update(
        {
            "started_at": "2026-04-01T00:00:00Z",
            "ended_at": "2026-04-15T00:00:00Z",
            "duration_hours": 336,
            "consecutive_calendar_days": 14,
            "session_clusters_observed": ["asia", "europe", "us"],
            "stress_or_event_day_documented": True,
            "report_verdict": "PASS",
            "report_sha256": "a" * 64,
            "git_sha": "84d7b66",
            "runtime_env_snapshot_sha256": "b" * 64,
            "shadow_trade_enable": True,
            "live_broker_enabled": True,
            "require_shadow_match_before_live": True,
            "operator_release_required": True,
            "execution_binding_required": True,
            "max_leverage": 7,
            "symbols_observed": ["BTCUSDT", "ETHUSDT"],
            "market_families_observed": ["futures"],
            "playbook_families_observed": ["trend_continuation", "breakout"],
            "candidate_for_live_count": 3,
            "shadow_only_count": 4,
            "do_not_trade_count": 5,
            "audit_sample_reviewed": True,
            "forensics_sample_reference": "forensics-ticket-123",
            "reviewed_by": "ops-review",
            "reviewed_at": "2026-04-15T01:00:00Z",
            "evidence_reference": "external-shadow-report-123",
            "owner_signoff": True,
        }
    )
    return payload


def test_shadow_certificate_template_blocks_live() -> None:
    status, blockers, warnings = assess_shadow_certificate(build_shadow_certificate_template())
    assert status == "FAIL"
    assert "duration_hours_missing" in blockers
    assert "session_clusters_less_than_3" in blockers
    assert "report_verdict_not_pass" in blockers
    assert "owner_signoff_missing_external_required" in warnings


def test_valid_shadow_certificate_passes_contract() -> None:
    status, blockers, warnings = assess_shadow_certificate(_valid_certificate())
    assert status == "PASS"
    assert blockers == []
    assert warnings == []


def test_shadow_certificate_rejects_72h_fixture_like_duration() -> None:
    payload = _valid_certificate()
    payload["duration_hours"] = 72
    status, blockers, _warnings = assess_shadow_certificate(payload)
    assert status == "FAIL"
    assert "duration_less_than_14_days" in blockers


def test_shadow_certificate_rejects_unredacted_secret_surface() -> None:
    assert certificate_secret_surface_issues({"database_url": "postgresql://u:secret@host/db"}) == [
        "secret_like_field_not_redacted:database_url"
    ]
    assert certificate_secret_surface_issues({"database_url": "[REDACTED]", "api_key": "not_stored_in_repo"}) == []


def test_cli_certificate_template_strict_fails(tmp_path: Path) -> None:
    out_json = tmp_path / "shadow_certificate.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--certificate-json",
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
    assert "duration_hours_missing" in payload["blockers"]
    assert "report_verdict_not_pass" in payload["blockers"]
