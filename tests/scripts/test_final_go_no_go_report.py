from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "final_go_no_go_report.py"


def test_final_go_no_go_report_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "final.md"
    out_json = tmp_path / "final.json"
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
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["mode_decisions"]["private_live_allowed"] == "NO"
    assert payload["mode_decisions"]["full_autonomous_live"] == "NO"
