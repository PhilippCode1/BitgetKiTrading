#!/usr/bin/env python3
"""
Minimale Monitoring-Checks (Cron / Heartbeat): Dashboard edge-status + Gateway /health.

Laedt .env.local fuer API_GATEWAY_URL. Exit 0 wenn beide erreichbar und sinnvoll OK.
Stdout: eine Zeile pro Check (maschinenlesbar).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        out[key] = val
    return out


def get_json(url: str, timeout: float = 8.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "monitor-http-endpoints/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw) if raw.strip() else {}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    env = load_dotenv(root / ".env.local")
    bind = (env.get("COMPOSE_EDGE_BIND") or "127.0.0.1").strip().strip('"').strip("'")
    if bind in ("0.0.0.0", "[::]", "::"):
        bind = "127.0.0.1"
    gw = (env.get("API_GATEWAY_URL") or f"http://{bind}:8000").rstrip("/")
    dash = (os.environ.get("MONITOR_DASHBOARD_ORIGIN") or "http://127.0.0.1:3000").rstrip("/")

    ok_all = True
    # Gateway
    try:
        req = urllib.request.Request(f"{gw}/health", headers={"User-Agent": "monitor/1"})
        with urllib.request.urlopen(req, timeout=6) as r:
            gh = r.status == 200
            print(f"gateway_health http_status={r.status} ok={gh}")
            ok_all = ok_all and gh
    except Exception as e:
        print(f"gateway_health ok=false error={e!s}")
        ok_all = False

    # Dashboard edge JSON (kein JWT)
    try:
        code, body = get_json(f"{dash}/api/dashboard/edge-status", timeout=10)
        gh = str(body.get("gatewayHealth") or "")
        edge_ok = code == 200 and gh in ("ok", "error", "down")
        print(f"dashboard_edge http_status={code} gatewayHealth={gh} ok={edge_ok}")
        ok_all = ok_all and edge_ok and gh == "ok"
    except Exception as e:
        print(f"dashboard_edge ok=false error={e!s}")
        ok_all = False

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
