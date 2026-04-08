#!/usr/bin/env python3
"""
Vor `docker compose up` / Bootstrap: Compose-Konfiguration validieren und typische Fehler melden.

- `docker compose ... config --services` muss erfolgreich sein (Syntax + Variablen-Interpolation).
- Heuristik: POSTGRES_PASSWORD leer in .env bei internem Postgres (Compose) → harter Fehler.

Aufruf: python tools/compose_start_preflight.py --env-file .env.local --profile local
Profile: local → + docker-compose.local-publish.yml; shadow|production → nur docker-compose.yml.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env_keys(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        out[key] = val
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, required=True)
    p.add_argument(
        "--profile",
        choices=("local", "shadow", "production"),
        required=True,
    )
    args = p.parse_args()
    env_path = args.env_file if args.env_file.is_absolute() else _REPO_ROOT / args.env_file
    if not env_path.is_file():
        print(f"compose_start_preflight: Datei fehlt: {env_path}", file=sys.stderr)
        return 1

    compose_args = ["-f", "docker-compose.yml"]
    if args.profile == "local":
        compose_args += ["-f", "docker-compose.local-publish.yml"]

    cmd = [
        "docker",
        "compose",
        *compose_args,
        "--env-file",
        str(env_path),
        "config",
        "--services",
    ]
    proc = subprocess.run(
        cmd,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print(
            "compose_start_preflight: docker compose config fehlgeschlagen.\n"
            "Pruefe docker-compose.yml, Overlay, fehlende Variablen in der ENV-Datei.\n",
            file=sys.stderr,
        )
        err = (proc.stderr or proc.stdout or "").strip()
        if err:
            print(err[-8000:], file=sys.stderr)
        return 1

    services = [s.strip() for s in proc.stdout.strip().splitlines() if s.strip()]
    print(
        f"compose_start_preflight: OK ({args.profile}) — {len(services)} Service(s) in der effektiven Compose-Config."
    )

    keys = _load_env_keys(env_path)
    pg_pw = (keys.get("POSTGRES_PASSWORD") or "").strip()
    dsn_docker = (keys.get("DATABASE_URL_DOCKER") or "").strip()
    dsn_l = dsn_docker.lower()
    expects_compose_postgres = (not dsn_docker) or ("@postgres:" in dsn_l)
    if expects_compose_postgres and not pg_pw:
        print(
            "compose_start_preflight: FEHLER — POSTGRES_PASSWORD ist leer, aber der Stack nutzt "
            "den Compose-Postgres (DATABASE_URL_DOCKER leer oder mit @postgres:).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
