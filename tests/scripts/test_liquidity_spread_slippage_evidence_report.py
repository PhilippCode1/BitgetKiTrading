from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "liquidity_spread_slippage_evidence_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"


def test_report_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "liquidity_spread_slippage_evidence.md"
    out_json = tmp_path / "liquidity_spread_slippage_evidence.json"
    completed = subprocess.run(
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
    assert completed.returncode == 0
    assert "liquidity_spread_slippage_evidence_report" in completed.stdout
    assert "# Liquidity Spread Slippage Evidence" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "assets" in payload
    assert payload["decision"] in {"not_enough_evidence", "verified"}
