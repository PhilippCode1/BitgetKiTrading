#!/usr/bin/env python3
"""
Laedt .env.local (oder angegebene Datei), setzt API_GATEWAY_URL / DASHBOARD_URL
wie Get-DevEdgeHost (COMPOSE_EDGE_BIND), startet rc_health_edge.

Gemeinsamer Einstieg fuer: rc_health.ps1, rc_health.sh, CI, pnpm smoke.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        qd = val.startswith('"') and val.endswith('"')
        qs = val.startswith("'") and val.endswith("'")
        if qd or qs:
            val = val[1:-1]
        out[key] = val
    return out


def _edge_host_from_env(data: dict[str, str]) -> str:
    raw = (data.get("COMPOSE_EDGE_BIND") or "").strip().strip('"').strip("'")
    if not raw:
        return "127.0.0.1"
    if raw in ("0.0.0.0", "[::]", "::"):
        return "127.0.0.1"
    return raw


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    env_name = argv[1] if len(argv) > 1 else ".env.local"
    env_path = root / env_name
    if not env_path.is_file():
        print(f"FEHLT: {env_path} (Pfad relativ zum Repo-Root)", file=sys.stderr)
        return 1
    data = _load_dotenv(env_path)
    for k, v in data.items():
        if k not in os.environ or not str(os.environ.get(k, "")).strip():
            os.environ[k] = v
    host = _edge_host_from_env(
        {"COMPOSE_EDGE_BIND": os.environ.get("COMPOSE_EDGE_BIND", "")}
    )
    gw_missing = "API_GATEWAY_URL" not in os.environ
    gw_empty = not str(os.environ.get("API_GATEWAY_URL", "")).strip()
    if gw_missing or gw_empty:
        os.environ["API_GATEWAY_URL"] = f"http://{host}:8000"
    dash_missing = "DASHBOARD_URL" not in os.environ
    dash_empty = not str(os.environ.get("DASHBOARD_URL", "")).strip()
    if dash_missing or dash_empty:
        os.environ["DASHBOARD_URL"] = f"http://{host}:3000"
    script = root / "scripts" / "rc_health_edge.py"
    gu = os.environ.get("API_GATEWAY_URL")
    du = os.environ.get("DASHBOARD_URL")
    print(f"rc_health_runner: API_GATEWAY_URL={gu} DASHBOARD_URL={du}", file=sys.stderr)
    return subprocess.call([sys.executable, str(script)])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
