from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.observability_alert_evidence_report import (
    assess_observability_ops_evidence,
    build_observability_ops_template,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "observability_alert_evidence_report.py"
ALERT_TEMPLATE = ROOT / "docs" / "production_10_10" / "alert_routing_evidence.template.json"
OBS_TEMPLATE = ROOT / "docs" / "production_10_10" / "observability_slos_evidence.template.json"


def _verified_alert_evidence() -> dict:
    return {
        "schema_version": "alert-routing-evidence-v1",
        "environment": "staging",
        "drill_started_at": "2026-04-26T10:00:00Z",
        "drill_completed_at": "2026-04-26T10:30:00Z",
        "git_sha": "abc1234",
        "operator": "owner",
        "evidence_reference": "https://example.invalid/evidence",
        "test_alert_label": "test_alert=true",
        "p0_route_verified": True,
        "p1_route_verified": True,
        "kill_switch_alert_delivered": True,
        "reconcile_alert_delivered": True,
        "market_data_stale_alert_delivered": True,
        "gateway_auth_alert_delivered": True,
        "delivery_channel": "slack",
        "delivery_proof_reference": "https://example.invalid/proof",
        "acknowledged_by_human": True,
        "ack_latency_seconds": 120.0,
        "ack_latency_budget_seconds": 900.0,
        "dedupe_verified": True,
        "runbook_link_verified": True,
        "main_console_alert_state_verified": True,
        "no_secret_in_alert_payload": True,
        "owner_signoff": True,
        "webhook_url": "[REDACTED]",
        "routing_key": "[REDACTED]",
        "authorization": "[REDACTED]",
        "notes_de": "synthetic",
    }


def _verified_obs_evidence() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "owner",
        "reviewed_at": "2026-04-26T12:00:00Z",
        "environment": "staging",
        "git_sha": "abc1234",
        "grafana": {
            "ops_dashboard_uri": "https://example.invalid/ops",
            "sli_dashboard_uri": "https://example.invalid/sli",
            "baseline_captured": True,
        },
        "slos": {
            "gateway_availability_slo_verified": True,
            "system_health_p95_slo_verified": True,
            "data_freshness_slo_verified": True,
            "live_safety_exposure_slo_verified": True,
        },
        "operations": {
            "on_call_path_documented": True,
            "incident_response_drill_reference": "https://example.invalid/drill",
            "runbook_links_peer_reviewed": True,
        },
        "safety": {
            "no_metrics_secrets_in_repo": True,
            "owner_signoff": True,
        },
    }


def test_default_payload_internal_clean_with_templates() -> None:
    payload = build_report_payload(
        alert_evidence_json=ALERT_TEMPLATE,
        observability_evidence_json=OBS_TEMPLATE,
    )
    assert not payload["internal_issues"]
    assert payload["alertmanager_verify"]["status"] == "PASS"
    assert payload["private_live_decision"] == "NO_GO"


def test_ops_assess_passes() -> None:
    r = assess_observability_ops_evidence(_verified_obs_evidence())
    assert r["status"] == "PASS"
    assert not r["failures"]


def test_ops_template_fails_assess() -> None:
    t = build_observability_ops_template()
    r = assess_observability_ops_evidence(t)
    assert r["status"] == "FAIL"


def test_cli_strict_and_strict_external(
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.json"
    o = tmp_path / "o.json"
    a.write_text(json.dumps(_verified_alert_evidence(), indent=2), encoding="utf-8")
    o.write_text(json.dumps(_verified_obs_evidence(), indent=2), encoding="utf-8")
    r0 = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r0.returncode == 0, r0.stderr
    r1 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--strict-external",
            "--alert-evidence-json",
            str(ALERT_TEMPLATE),
            "--observability-evidence-json",
            str(OBS_TEMPLATE),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 1
    r2 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--strict-external",
            f"--alert-evidence-json={a}",
            f"--observability-evidence-json={o}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stderr
