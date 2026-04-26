from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.audit_forensics_replay_evidence_report import (
    assess_external_evidence,
    build_external_evidence_template,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_forensics_replay_evidence_report.py"
DEFAULT_TEMPLATE = ROOT / "docs" / "production_10_10" / "audit_forensics_replay_evidence.template.json"


def _verified_external_payload() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "owner-test",
        "reviewed_at": "2026-04-26T12:00:00Z",
        "environment": "staging",
        "git_sha": "abc1234",
        "staging_replay": {
            "performed": True,
            "window_start": "2026-04-26T10:00:00Z",
            "window_end": "2026-04-26T11:00:00Z",
            "trace_ids_sampled": ["trace-1"],
            "signal_risk_exchange_chain_verified": True,
            "live_orders_during_replay": False,
            "report_uri": "https://example.invalid/replay-report",
        },
        "ledger": {
            "storage_durable": True,
            "append_only_policy": True,
            "retention_days": 90,
            "export_uri": "https://example.invalid/ledger-export",
        },
        "forensics": {
            "searchable_by_trace": True,
            "operator_summary_de_available": True,
            "incident_drill_reference": "https://example.invalid/drill",
        },
        "safety": {
            "secrets_redacted": True,
            "owner_signoff": True,
            "real_orders_possible": False,
        },
    }


def test_default_payload_internal_clean_external_not_pass() -> None:
    payload = build_report_payload(external_evidence_json=DEFAULT_TEMPLATE)
    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert not payload["internal_issues"]
    assert payload["external_evidence_assessment"]["status"] == "FAIL"
    assert payload["external_evidence_assessment"]["external_required"] is True
    complete = payload["replay_scenarios"]["complete"]
    assert complete["replay_sufficient"] is True
    assert payload["replay_scenarios"]["incomplete"]["replay_sufficient"] is False
    assert "llm_explanation_not_audit_truth" in payload["replay_scenarios"]["llm_explanation_flag"]["warnings"]


def test_assess_external_passes_on_verified_fixture() -> None:
    result = assess_external_evidence(_verified_external_payload())
    assert result["status"] == "PASS"
    assert not result["failures"]


def test_assess_external_fails_on_live_orders_during_replay() -> None:
    bad = _verified_external_payload()
    bad["staging_replay"]["live_orders_during_replay"] = True
    result = assess_external_evidence(bad)
    assert result["status"] == "FAIL"
    assert "staging_replay_darf_keine_live_orders_haben" in result["failures"]


def test_build_template_roundtrip() -> None:
    tpl = build_external_evidence_template()
    assert tpl["schema_version"] == 1
    a = assess_external_evidence(tpl)
    assert a["status"] == "FAIL"


def test_cli_strict_and_strict_external(tmp_path: Path) -> None:
    verified = tmp_path / "verified.json"
    verified.write_text(json.dumps(_verified_external_payload(), indent=2), encoding="utf-8")
    out_md = tmp_path / "out.md"
    out_json = tmp_path / "out.json"
    r1 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            f"--external-evidence-json={verified}",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--strict-external",
            f"--external-evidence-json={DEFAULT_TEMPLATE}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 1
    r3 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--strict-external",
            f"--external-evidence-json={verified}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r3.returncode == 0, r3.stdout + r3.stderr
