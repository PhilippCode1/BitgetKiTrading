#!/usr/bin/env python3
"""
Vault-Mandanten-Credentials pruefen (ohne Secret-Werte auszugeben).

Prueft:
  - VAULT_MODE / VAULT_ADDR / VAULT_TOKEN konfiguriert (kein Platzhalter)
  - KV-Pfad bitget/{tenant_id}/live lesbar
  - api_key / api_secret / api_passphrase vorhanden

Beispiel:
  python tools/verify_vault_tenant_credentials.py --env-file .env.production --tenant-id <TENANT>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SHARED_SRC = ROOT / "shared" / "python" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.secret_store import read_hashicorp_kv_v2, vault_config_from_env  # noqa: E402
from shared_py.tenant_exchange_credentials import (  # noqa: E402
    vault_secret_path_for_tenant,
)

_PLACEHOLDER_RE = re.compile(
    r"(YOUR_|CHANGE_ME|<SET_|placeholder|example\.com|example\.invalid)",
    re.IGNORECASE,
)


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        out[key] = val
    return out


def _apply_env(env: dict[str, str]) -> None:
    for k, v in env.items():
        os.environ[k] = v


def _is_placeholder(val: str) -> bool:
    s = (val or "").strip()
    if not s:
        return True
    return bool(_PLACEHOLDER_RE.search(s))


def _bundle_fields_present(data: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    key = str(data.get("api_key") or data.get("BITGET_API_KEY") or "").strip()
    secret = str(data.get("api_secret") or data.get("BITGET_API_SECRET") or "").strip()
    phrase = str(
        data.get("api_passphrase") or data.get("BITGET_API_PASSPHRASE") or ""
    ).strip()
    if not key:
        missing.append("api_key")
    if not secret:
        missing.append("api_secret")
    if not phrase:
        missing.append("api_passphrase")
    return len(missing) == 0, missing


def verify_vault_tenant_credentials(
    *,
    tenant_id: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if env:
        _apply_env(env)

    tid = (tenant_id or env.get("MODUL_MATE_GATE_TENANT_ID") if env else "").strip()
    if not tid or tid == "default":
        tid = (tenant_id or os.environ.get("MODUL_MATE_GATE_TENANT_ID") or "").strip()
    if not tid or tid == "default":
        return {
            "ok": False,
            "error": "tenant_id_required",
            "message": "Setze --tenant-id oder MODUL_MATE_GATE_TENANT_ID.",
        }

    mode = (os.environ.get("VAULT_MODE") or "").strip().lower()
    addr = (os.environ.get("VAULT_ADDR") or "").strip()
    token = (os.environ.get("VAULT_TOKEN") or "").strip()

    issues: list[str] = []
    if mode not in ("hashicorp", "vault", "hc"):
        issues.append("VAULT_MODE muss hashicorp/vault/hc sein.")
    if not addr or _is_placeholder(addr):
        issues.append("VAULT_ADDR fehlt oder ist Platzhalter.")
    if not token or _is_placeholder(token):
        issues.append("VAULT_TOKEN fehlt oder ist Platzhalter.")
    if issues:
        return {
            "ok": False,
            "tenant_id": tid,
            "error": "vault_config_invalid",
            "issues": issues,
        }

    cfg = vault_config_from_env()
    if cfg is None:
        return {
            "ok": False,
            "tenant_id": tid,
            "error": "vault_config_unavailable",
            "message": "vault_config_from_env() lieferte None.",
        }

    path = vault_secret_path_for_tenant(tid)
    data = read_hashicorp_kv_v2(secret_path=path, cfg=cfg)
    if not data:
        return {
            "ok": False,
            "tenant_id": tid,
            "vault_path": path,
            "error": "vault_read_failed",
            "message": (
                f"KV-Pfad {path} nicht lesbar (Token, Mount, Pfad oder Netzwerk pruefen)."
            ),
        }

    complete, missing = _bundle_fields_present(data)
    if not complete:
        return {
            "ok": False,
            "tenant_id": tid,
            "vault_path": path,
            "error": "credential_fields_missing",
            "missing_fields": missing,
        }

    return {
        "ok": True,
        "tenant_id": tid,
        "vault_path": path,
        "credential_fields": ["api_key", "api_secret", "api_passphrase"],
        "source": "vault_tenant",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Vault-Mandanten-Bitget-Credentials pruefen")
    ap.add_argument("--env-file", default=".env.production", help="ENV-Datei laden")
    ap.add_argument(
        "--tenant-id",
        default="",
        help="Mandanten-ID (Default: MODUL_MATE_GATE_TENANT_ID aus ENV)",
    )
    ap.add_argument("--json", action="store_true", help="JSON auf stdout")
    args = ap.parse_args()

    env_path = Path(args.env_file)
    if not env_path.is_file():
        payload = {"ok": False, "error": "env_file_missing", "path": str(env_path)}
        print(json.dumps(payload, indent=2))
        return 2

    env = _load_env_file(env_path)
    result = verify_vault_tenant_credentials(tenant_id=args.tenant_id, env=env)

    if args.json:
        print(json.dumps(result, indent=2))
    elif result.get("ok"):
        print(
            f"PASS tenant={result['tenant_id']} path={result['vault_path']} "
            "(Felder vorhanden, keine Werte geloggt)"
        )
    else:
        print(f"FAIL: {result.get('error', 'unknown')}")
        for key in ("message", "issues", "missing_fields"):
            val = result.get(key)
            if val:
                print(f"  {key}: {val}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
