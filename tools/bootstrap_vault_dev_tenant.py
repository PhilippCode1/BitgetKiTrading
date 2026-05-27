#!/usr/bin/env python3
"""
Seed fuer lokalen Vault-Dev: schreibt bitget/{tenant_id}/live (KV v2).

Liest Bitget-Credentials aus ENV oder --env-file (BITGET_API_*), schreibt
ohne Werte zu loggen. Anschliessend optional verify_vault_tenant_credentials.

Beispiel:
  docker compose -f docker-compose.yml -f docker-compose.vault-dev.yml up -d vault
  python tools/bootstrap_vault_dev_tenant.py --env-file .env.vault-dev.example --env-file .env.local --tenant-id t-dev-1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SHARED_SRC = ROOT / "shared" / "python" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.secret_store import (  # noqa: E402
    vault_config_from_env,
    write_hashicorp_kv_v2,
)
from shared_py.tenant_exchange_credentials import vault_secret_path_for_tenant  # noqa: E402


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
        val = v.strip().strip('"').strip("'")
        out[key] = val
    return out


def _apply_env_files(paths: list[Path]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(_load_env_file(path))
    for k, v in merged.items():
        os.environ[k] = v
    return merged


def _bitget_bundle_from_env(env: dict[str, str]) -> dict[str, str] | None:
    key = (env.get("BITGET_API_KEY") or os.environ.get("BITGET_API_KEY") or "").strip()
    secret = (
        env.get("BITGET_API_SECRET") or os.environ.get("BITGET_API_SECRET") or ""
    ).strip()
    phrase = (
        env.get("BITGET_API_PASSPHRASE") or os.environ.get("BITGET_API_PASSPHRASE") or ""
    ).strip()
    if not key or not secret or not phrase:
        return None
    return {"api_key": key, "api_secret": secret, "api_passphrase": phrase}


def bootstrap_vault_tenant(
    *,
    tenant_id: str,
    env_files: list[Path],
    verify: bool,
) -> dict[str, Any]:
    env = _apply_env_files(env_files)
    tid = (
        (tenant_id or "").strip()
        or (env.get("MODUL_MATE_GATE_TENANT_ID") or "").strip()
        or (env.get("COMMERCIAL_DEFAULT_TENANT_ID") or "").strip()
    )
    if not tid or tid == "default" or tid.startswith("<"):
        return {
            "ok": False,
            "error": "tenant_id_required",
            "message": "Setze --tenant-id oder MODUL_MATE_GATE_TENANT_ID.",
        }

    os.environ.setdefault("VAULT_MODE", "hashicorp")
    os.environ.setdefault("VAULT_ADDR", "http://127.0.0.1:8200")
    os.environ.setdefault("VAULT_TOKEN", "dev-root-token")
    os.environ.setdefault("VAULT_KV_MOUNT", "secret")

    bundle = _bitget_bundle_from_env(env)
    if bundle is None:
        return {
            "ok": False,
            "error": "bitget_credentials_missing",
            "message": (
                "BITGET_API_KEY/SECRET/PASSPHRASE in ENV oder --env-file setzen "
                "(Staging-Keys, nicht committen)."
            ),
        }

    cfg = vault_config_from_env()
    if cfg is None:
        return {"ok": False, "error": "vault_config_unavailable"}

    path = vault_secret_path_for_tenant(tid)
    if not write_hashicorp_kv_v2(secret_path=path, data=bundle, cfg=cfg):
        return {
            "ok": False,
            "error": "vault_write_failed",
            "vault_path": path,
            "message": "Vault nicht erreichbar? docker compose ... vault-dev up -d vault",
        }

    result: dict[str, Any] = {
        "ok": True,
        "tenant_id": tid,
        "vault_path": path,
        "vault_addr": cfg.addr,
    }

    if verify:
        tools_dir = ROOT / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        import verify_vault_tenant_credentials as verify_mod  # noqa: WPS433

        check = verify_mod.verify_vault_tenant_credentials(tenant_id=tid)
        result["verify"] = check
        if not check.get("ok"):
            result["ok"] = False
            result["error"] = "verify_failed"

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Mehrfach: spaeteres File ueberschreibt frueheres.",
    )
    ap.add_argument("--tenant-id", default="")
    ap.add_argument("--verify", action="store_true", default=True)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    paths = [Path(p) for p in args.env_file]
    if not paths:
        paths = [ROOT / ".env.vault-dev.example", ROOT / ".env.local"]

    result = bootstrap_vault_tenant(
        tenant_id=args.tenant_id,
        env_files=paths,
        verify=not args.no_verify,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("ok"):
        print(
            f"PASS seeded tenant={result['tenant_id']} path={result['vault_path']} "
            f"addr={result.get('vault_addr')}"
        )
    else:
        print(f"FAIL: {result.get('error', 'unknown')}")
        if result.get("message"):
            print(f"  {result['message']}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
