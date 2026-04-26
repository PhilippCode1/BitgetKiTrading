from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.deployment_supply_chain_evidence_report import (
    assess_deployment_evidence,
    assess_supply_evidence,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "deployment_supply_chain_evidence_report.py"
DEP_T = ROOT / "docs" / "production_10_10" / "deployment_staging_parity_evidence.template.json"
SUP_T = ROOT / "docs" / "production_10_10" / "supply_chain_release_audit_evidence.template.json"


def _verified_dep() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "owner",
        "reviewed_at": "2026-04-26T12:00:00Z",
        "environment": "shadow",
        "git_sha": "abc",
        "checks": {
            "staging_or_shadow_smoke_pass": True,
            "api_integration_smoke_or_equivalent": True,
            "disallow_loopback_gateway_for_deploy_profile": True,
            "compose_runtime_effective_env_reviewed": True,
        },
        "artifacts": {
            "smoke_log_uri": "https://example.invalid/smoke.log",
            "docker_compose_effective_excerpt_uri": "https://example.invalid/compose.txt",
        },
        "safety": {
            "no_secrets_in_logs": True,
            "owner_signoff": True,
        },
    }


def _verified_sup() -> dict:
    return {
        "schema_version": 1,
        "status": "verified",
        "reviewed_by": "owner",
        "reviewed_at": "2026-04-26T12:00:00Z",
        "git_sha": "abc",
        "ci": {
            "last_pip_audit_gate_pass": True,
            "last_pnpm_audit_high_gate_pass": True,
            "ci_run_uri": "https://example.invalid/ci/1",
        },
        "findings": {
            "open_high_or_critical_supplier_issues": 0,
            "last_sbom_or_export_uri": "https://example.invalid/sbom.json",
        },
        "safety": {
            "no_tokens_in_report_exports": True,
            "owner_signoff": True,
        },
    }


def test_templates_fail_assess() -> None:
    d = json.loads(DEP_T.read_text(encoding="utf-8"))
    assert assess_deployment_evidence(d)["status"] == "FAIL"
    s = json.loads(SUP_T.read_text(encoding="utf-8"))
    assert assess_supply_evidence(s)["status"] == "FAIL"


def test_verified_assess_pass() -> None:
    assert assess_deployment_evidence(_verified_dep())["status"] == "PASS"
    assert assess_supply_evidence(_verified_sup())["status"] == "PASS"


def test_build_payload_no_internal_when_repo_ok() -> None:
    p = build_report_payload()
    assert not p["internal_issues"]


def test_cli_strict_external(tmp_path: Path) -> None:
    d = tmp_path / "d.json"
    s = tmp_path / "s.json"
    d.write_text(json.dumps(_verified_dep(), indent=2), encoding="utf-8")
    s.write_text(json.dumps(_verified_sup(), indent=2), encoding="utf-8")
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
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--strict-external",
            f"--deployment-json={d}",
            f"--supply-json={s}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stderr
