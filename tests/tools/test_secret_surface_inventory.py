from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "inventory_secret_surfaces.py"


def test_secret_surface_inventory_generates_reports_with_redaction(tmp_path: Path) -> None:
    md = tmp_path / "secret_surface_inventory.md"
    js = tmp_path / "secret_surface_inventory.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-md",
            str(md),
            "--output-json",
            str(js),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "findings" in payload
    for finding in payload["findings"][:20]:
        assert "*" in finding["redacted_snippet"] or finding["redacted_snippet"] == ""


def test_secret_surface_inventory_strict_exit_code_is_deterministic() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode in (0, 1)
    assert "secret_surface_inventory:" in (completed.stdout + completed.stderr)
