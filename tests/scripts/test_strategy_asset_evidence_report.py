from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "strategy_asset_evidence_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "strategy_asset_evidence_sample.json"


def test_report_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run ok" in completed.stdout


def test_report_generates_german_block_reasons(tmp_path: Path) -> None:
    out_md = tmp_path / "out.md"
    out_json = tmp_path / "out.json"
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
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    combined = " ".join(item["summary_de"] for item in payload["items"])
    assert "blockiert" in combined or "Gate-Schritt" in combined
    assert payload["verified"] is False
    assert payload["status"] in {"NOT_ENOUGH_EVIDENCE", "implemented"}
    assert payload["checked_asset_classes"]
    assert all("decision" in item for item in payload["items"])
    assert any(item["decision"] in {"BLOCK_FOR_LIVE", "BLOCK_ALL", "ALLOW_FOR_PAPER"} for item in payload["items"])
