from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "dr.md"
    output_json = tmp_path / "dr.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "disaster_recovery_drill_report.py"),
            "--output-md",
            str(output_md),
            "--output-json",
            str(output_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["status"] == "NOT_ENOUGH_EVIDENCE"
    assert payload["verified"] is False
    assert payload["evidence_level"] == "synthetic"
