from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "incident_drill_report.py"


def test_incident_drill_report_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "incident.md"
    out_json = tmp_path / "incident.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
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
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "NOT_ENOUGH_EVIDENCE"
    assert payload["verified"] is False
    assert payload["evidence_level"] == "synthetic"
