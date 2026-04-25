from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "liquidity_quality_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"


def test_report_script_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run=true" in completed.stdout


def test_report_contains_no_secrets(tmp_path: Path) -> None:
    out_md = tmp_path / "liquidity.md"
    out_json = tmp_path / "liquidity.json"
    subprocess.run(
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
        check=True,
    )
    text = out_md.read_text(encoding="utf-8").lower()
    assert "secret" not in text
    assert "password" not in text
    assert "token" not in text
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "assets" in payload
