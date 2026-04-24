#!/usr/bin/env python3
"""
Laedt .env.local (oder angegebene Datei), setzt API_GATEWAY_URL / DASHBOARD_URL
wie Get-DevEdgeHost (COMPOSE_EDGE_BIND), startet rc_health_edge.

Gemeinsamer Einstieg fuer: rc_health.ps1, rc_health.sh, CI, pnpm smoke.
Exit-Code: wie rc_health_edge (0 gruen, 1 Fehler/Degradation / stress-Fail).
"""
from __future__ import annotations

import argparse
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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Lade ENV und starte rc_health_edge (Quality Gate).",
    )
    p.add_argument(
        "env_file",
        nargs="?",
        default=".env.local",
        help="dotenv-Datei relativ zum Repo-Root (Default: .env.local)",
    )
    p.add_argument(
        "--stress",
        action="store_true",
        help="Weiterreichen: mehrfache vollstaendige Health-Pruefungen (siehe rc_health_edge).",
    )
    p.add_argument(
        "--stress-rounds",
        type=int,
        help="Fuer --stress, optional (Default aus rc_health_edge).",
    )
    p.add_argument(
        "--stress-interval-sec",
        type=float,
        help="Fuer --stress, optional.",
    )
    p.add_argument(
        "--startup-budget-sec",
        type=float,
        default=None,
        help="Weiterreichen: Startup-Warte/Retry (Default 120s, siehe rc_health_edge).",
    )
    p.add_argument(
        "--stable-window-sec",
        type=str,
        default="",
        help="Weiterreichen: z. B. 10 oder 10s — dauernd gruen; siehe rc_health_edge.",
    )
    return p.parse_args(argv)


def main(arg_list: list[str] | None = None) -> int:
    argv = arg_list if arg_list is not None else sys.argv[1:]
    args = _parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    env_name = (args.env_file or "").strip() or ".env.local"
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
    ext: list[str] = []
    if args.stress:
        ext.append("--stress")
        if args.stress_rounds is not None:
            ext += ["--stress-rounds", str(int(args.stress_rounds))]
        if args.stress_interval_sec is not None:
            ext += ["--stress-interval-sec", str(float(args.stress_interval_sec))]
    if args.startup_budget_sec is not None:
        ext += ["--startup-budget-sec", str(float(args.startup_budget_sec))]
    if (args.stable_window_sec or "").strip():
        ext += ["--stable-window-sec", str(args.stable_window_sec).strip()]
    rc = subprocess.call([sys.executable, str(script), *ext])
    return 0 if int(rc) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
