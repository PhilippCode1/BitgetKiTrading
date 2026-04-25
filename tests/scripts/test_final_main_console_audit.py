from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "final_main_console_audit.py"


def test_final_audit_dry_json_is_parseable() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["project_name"] == "bitget-btc-ai"
    assert "mode_decisions" in payload
    assert "scores" in payload


def test_final_audit_outputs_markdown(tmp_path: Path) -> None:
    out = tmp_path / "final.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = out.read_text(encoding="utf-8")
    assert "# Final Main Console Audit" in text
    assert "## Go/No-Go je Modus" in text
    assert "## Scores" in text


def test_mode_decisions_contain_required_modes() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    mode = payload["mode_decisions"]
    assert "local" in mode
    assert "paper" in mode
    assert "shadow" in mode
    assert "staging" in mode
    assert "kontrollierter_live_pilot" in mode
    assert "vollautomatisches_live" in mode
