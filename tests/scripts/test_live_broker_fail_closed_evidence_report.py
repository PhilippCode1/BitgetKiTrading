from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "live_broker_fail_closed_evidence_report.py"


def test_report_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "live_broker_fail_closed_evidence.md"
    out_json = tmp_path / "live_broker_fail_closed_evidence.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-md", str(out_md), "--output-json", str(out_json)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["verified"] is False
    assert payload["evidence_level"] == "synthetic"
    assert len(payload["scenarios"]) >= 20
