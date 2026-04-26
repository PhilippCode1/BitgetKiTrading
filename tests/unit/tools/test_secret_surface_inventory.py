from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "inventory_secret_surfaces.py"


def test_inventory_script_runs() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    raw = (r.stdout or "") + (r.stderr or "")
    assert "secret_surface_inventory:" in raw
    jstart = raw.find("{")
    assert jstart >= 0, raw
    dec = json.JSONDecoder()
    payload, _ = dec.raw_decode(raw[jstart:])
    assert "findings" in payload
    assert "severity_counts" in payload


def test_generates_markdown(tmp_path: Path) -> None:
    out = tmp_path / "inv.md"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-md", str(out)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    t = out.read_text(encoding="utf-8")
    assert "# Secret Surface Inventory" in t
    assert "Findings" in t
