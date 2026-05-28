#!/usr/bin/env python3
"""Prueft ob Vault unter VAULT_ADDR erreichbar ist (ohne Secrets)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def check_vault_runtime(*, env_file: Path | None = None) -> dict[str, object]:
    env: dict[str, str] = {}
    if env_file and env_file.is_file():
        env = _load_env_file(env_file)

    addr = (env.get("VAULT_ADDR") or os.environ.get("VAULT_ADDR") or "").strip().rstrip("/")
    if not addr:
        return {"ok": False, "error": "VAULT_ADDR_missing"}

    url = f"{addr}/v1/sys/health"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
        data = resp.json() if resp.content else {}
        ok = resp.status_code in (200, 429, 472, 473)
        return {
            "ok": ok,
            "vault_addr": addr,
            "http_status": resp.status_code,
            "initialized": data.get("initialized"),
            "sealed": data.get("sealed"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "vault_addr": addr,
            "error": type(exc).__name__,
            "hint": "Docker Desktop starten: pnpm vault:dev:up",
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = check_vault_runtime(env_file=args.env_file)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result.get("ok"):
        print(f"PASS Vault erreichbar: {result.get('vault_addr')}")
    else:
        print(f"FAIL Vault nicht erreichbar: {result.get('vault_addr', '—')}")
        if result.get("hint"):
            print(f"  Hinweis: {result['hint']}")
        if result.get("error"):
            print(f"  Fehler: {result['error']}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
