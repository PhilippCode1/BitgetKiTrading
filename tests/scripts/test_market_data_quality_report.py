from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "market_data_quality_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "market_data_quality_sample.json"


def test_script_dry_run_works() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run=true" in completed.stdout


def test_report_contains_german_block_reasons_and_no_secrets(tmp_path: Path) -> None:
    out_md = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
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
    content = out_md.read_text(encoding="utf-8")
    assert "Deutsche Zusammenfassung fuer Philipp" in content
    lowered = content.lower()
    assert "secret" not in lowered
    assert "password" not in lowered
    assert "token" not in lowered
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["assets_checked"] >= 1
