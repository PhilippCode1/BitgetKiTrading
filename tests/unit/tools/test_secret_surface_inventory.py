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
    assert "inventoried_secret_surface_rows=" in raw
    jstart = raw.find("{")
    assert jstart >= 0, raw
    dec = json.JSONDecoder()
    payload, _ = dec.raw_decode(raw[jstart:])
    assert "rows" in payload
    keys = {row["env"] for row in payload["rows"]}
    assert "POSTGRES_PASSWORD" in keys
    assert "NEXT_PUBLIC_API_BASE_URL" in keys
    by_env = {row["env"]: row for row in payload["rows"]}
    assert by_env["POSTGRES_PASSWORD"]["kind"] == "secret"
    assert by_env["NEXT_PUBLIC_API_BASE_URL"]["kind"] == "public_config"


def test_generates_markdown(tmp_path: Path) -> None:
    out = tmp_path / "inv.md"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--report-md", str(out)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    t = out.read_text(encoding="utf-8")
    assert "# Secret-Surface-Inventar" in t
    assert "| `JWT_SECRET` |" in t or "JWT_SECRET" in t
    assert "Wrote" in (r.stderr or "")
