from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "asset_data_quality_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "asset_data_quality_sample.json"


def test_report_contains_required_fields(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--input-json", str(FIXTURE), "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.returncode == 0
    content = out.read_text(encoding="utf-8")
    assert "Datum/Zeit" in content
    assert "Git SHA" in content
    assert "Asset/Symbol" in content
    assert "MarketFamily" in content
    assert "ProductType" in content
    assert "Datenquelle" in content
    assert "Quality Status" in content
    assert "Block Reasons" in content
    assert "Warnings" in content
    assert "Live-Auswirkung" in content
    assert "Ergebnis" in content


def test_dry_run_works() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.returncode == 0
    assert "Asset Data Quality Report" in completed.stdout
