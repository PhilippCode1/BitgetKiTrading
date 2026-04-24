#!/usr/bin/env python3
"""JWT fuer DASHBOARD_GATEWAY_AUTHORIZATION (HS256, wie api-gateway/auth.py).

Enthaelt u. a. 'role': 'admin' (RBAC /v1/admin) und gateway_roles.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import jwt


def load_dotenv_simple(path: Path) -> dict[str, str]:
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
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        out[key] = val
    return out


def mint_token(env: dict[str, str], *, ttl_days: int) -> str:
    secret = (env.get("GATEWAY_JWT_SECRET") or "").strip()
    if not secret:
        raise SystemExit("GATEWAY_JWT_SECRET fehlt in der ENV-Datei.")
    aud = (env.get("GATEWAY_JWT_AUDIENCE") or "api-gateway").strip()
    iss = (env.get("GATEWAY_JWT_ISSUER") or "bitget-btc-ai-gateway").strip()
    now = int(time.time())
    payload = {
        "sub": "dashboard-local",
        "role": "admin",
        "gateway_roles": ["gateway:read", "admin:read", "admin:write", "operator:mutate"],
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + ttl_days * 86400,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def update_env_file(path: Path, line: str) -> None:
    raw = path.read_text(encoding="utf-8")
    key = line.split("=", 1)[0]
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pat.search(raw):
        new_body = pat.sub(line, raw)
    else:
        new_body = raw.rstrip() + "\n\n# Dashboard -> Gateway (serverseitig, nicht im Browser)\n" + line + "\n"
    path.write_text(new_body, encoding="utf-8", newline="\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, default=Path(".env.local"))
    p.add_argument("--ttl-days", type=int, default=365)
    p.add_argument("--print-line", action="store_true", help="Nur DASHBOARD_GATEWAY_AUTHORIZATION=Bearer ... ausgeben")
    p.add_argument(
        "--update-env-file",
        action="store_true",
        help="Schreibt/ersetzt DASHBOARD_GATEWAY_AUTHORIZATION in --env-file",
    )
    args = p.parse_args()
    if not args.env_file.is_file():
        print(f"Datei fehlt: {args.env_file}", file=sys.stderr)
        return 1
    env = load_dotenv_simple(args.env_file)
    token = mint_token(env, ttl_days=args.ttl_days)
    full_line = f"DASHBOARD_GATEWAY_AUTHORIZATION=Bearer {token}"
    if args.update_env_file:
        update_env_file(args.env_file, full_line)
        print(f"Aktualisiert: {args.env_file} ({key_from_line(full_line)})")
        return 0
    if args.print_line:
        print(full_line)
        return 0
    print(token)
    return 0


def key_from_line(line: str) -> str:
    return line.split("=", 1)[0]


if __name__ == "__main__":
    raise SystemExit(main())
