from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_multi_asset_strategy_evidence.py"
FIXTURE = ROOT / "tests" / "fixtures" / "multi_asset_strategy_evidence_sample.json"


def test_script_dry_run_works() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry-run=true" in proc.stdout


def test_script_generates_report_with_german_blockgruende(tmp_path: Path) -> None:
    out_md = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
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
    # fixture contains one FAIL item
    assert proc.returncode == 1
    content = out_md.read_text(encoding="utf-8")
    assert "Blockgründe (de)" in content
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "summary" in payload
    assert payload["summary"]["FAIL"] >= 1
    assert payload["verified"] is False
    assert payload["status"] in {"NOT_ENOUGH_EVIDENCE", "implemented"}
    assert "version_binding_ok" in payload


def test_script_can_generate_fail_closed_report_without_failing_cli(tmp_path: Path) -> None:
    out_md = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
            "--allow-failures",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["FAIL"] >= 1
