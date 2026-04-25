from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "asset_governance_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "asset_governance_sample.json"


def test_report_generates_german_summary(tmp_path: Path) -> None:
    output_md = tmp_path / "asset_governance_sample.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
            "--output-md",
            str(output_md),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "asset_governance_report" in completed.stdout
    text = output_md.read_text(encoding="utf-8")
    assert "Anzahl Assets je Zustand" in text
    assert "Naechste Freigabeaufgaben fuer Philipp" in text


def test_report_contains_no_secrets(tmp_path: Path) -> None:
    output_md = tmp_path / "asset_governance_sample.md"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            str(FIXTURE),
            "--output-md",
            str(output_md),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    text = output_md.read_text(encoding="utf-8").lower()
    assert "secret" not in text
    assert "password" not in text
    assert "token" not in text
