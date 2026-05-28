#!/usr/bin/env python3
"""
Go-Live Ops-Wizard: GO/NO-GO + optionale sichere Auto-Fixes (ohne Vault/Bitget-Secrets).

--apply-safe (optional):
  - DASHBOARD_GATEWAY_AUTHORIZATION minten (wenn GATEWAY_JWT_SECRET gesetzt)
  - REDIS_PASSWORD generieren (wenn Platzhalter)
  - --vault-dev: VAULT_* aus .env.vault-dev.example mergen (nur Dev)

Beispiele:
  python tools/go_live_ops_wizard.py --env-file .env.production --strict-runtime
  python tools/go_live_ops_wizard.py --env-file .env.production --strict-runtime --apply-safe
  python tools/go_live_ops_wizard.py --env-file .env.production --strict-runtime --apply-safe --vault-dev
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEV_TENANT_ID = "t-dev-local"
DEV_UNUSED_VAULT_APPROLE = "dev-unused-approle"

_PLACEHOLDER = re.compile(
    r"(YOUR_|CHANGE_ME|<SET_|placeholder|replace_after_mint)",
    re.IGNORECASE,
)


def _load_trade_ready():
    path = ROOT / "tools" / "go_live_trade_ready.py"
    name = "go_live_trade_ready"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_dotenv(path: Path) -> dict[str, str]:
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


def _is_placeholder(val: str) -> bool:
    s = (val or "").strip()
    if not s:
        return True
    if s.startswith("<") and s.endswith(">"):
        return True
    return bool(_PLACEHOLDER.search(s))


def _update_env_key(path: Path, key: str, value: str) -> None:
    raw = path.read_text(encoding="utf-8")
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pat.search(raw):
        path.write_text(pat.sub(line, raw), encoding="utf-8", newline="\n")
    else:
        path.write_text(raw.rstrip() + f"\n{line}\n", encoding="utf-8", newline="\n")


def apply_safe_fixes(
    env_file: Path,
    *,
    vault_dev: bool,
) -> list[str]:
    applied: list[str] = []
    env = _load_dotenv(env_file)

    env = _load_dotenv(env_file)

    if vault_dev:
        vault_example = ROOT / ".env.vault-dev.example"
        vault_env = _load_dotenv(vault_example)
        merge_keys = list(
            dict.fromkeys(
                list(vault_env.keys())
                + [
                    "VAULT_ROLE_ID",
                    "VAULT_SECRET_ID",
                    "MODUL_MATE_GATE_TENANT_ID",
                    "COMMERCIAL_DEFAULT_TENANT_ID",
                    "OIDC_DEFAULT_TENANT_ID",
                ]
            )
        )
        for key in merge_keys:
            if key in vault_env and not _is_placeholder(vault_env[key]):
                val = vault_env[key]
            elif key in (
                "MODUL_MATE_GATE_TENANT_ID",
                "COMMERCIAL_DEFAULT_TENANT_ID",
                "OIDC_DEFAULT_TENANT_ID",
            ):
                val = DEV_TENANT_ID
            elif key in ("VAULT_ROLE_ID", "VAULT_SECRET_ID"):
                val = DEV_UNUSED_VAULT_APPROLE
            else:
                continue
            if _is_placeholder(env.get(key, "")) or (
                vault_dev and key in ("VAULT_ADDR", "VAULT_MODE", "VAULT_TOKEN")
            ):
                _update_env_key(env_file, key, val)
                applied.append(f"{key}=<vault-dev>")
        env = _load_dotenv(env_file)

    for key in ("APEX_AUDIT_LEDGER_ED25519_SEED_HEX", "RESEARCH_BENCHMARK_READ_SECRET"):
        if _is_placeholder(env.get(key, "")):
            val = (
                secrets.token_hex(32)
                if key.endswith("_HEX")
                else secrets.token_urlsafe(32)
            )
            _update_env_key(env_file, key, val)
            applied.append(f"{key} (generated)")

    secret = env.get("GATEWAY_JWT_SECRET", "")
    auth = env.get("DASHBOARD_GATEWAY_AUTHORIZATION", "")
    if not _is_placeholder(secret) and _is_placeholder(auth):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "mint_dashboard_gateway_jwt.py"),
                "--env-file",
                str(env_file.resolve()),
                "--update-env-file",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            applied.append("DASHBOARD_GATEWAY_AUTHORIZATION (minted)")
        else:
            applied.append(
                "DASHBOARD_GATEWAY_AUTHORIZATION mint failed "
                f"(exit {proc.returncode})"
            )

    if _is_placeholder(env.get("REDIS_PASSWORD", "")):
        _update_env_key(env_file, "REDIS_PASSWORD", secrets.token_urlsafe(32))
        applied.append("REDIS_PASSWORD (generated)")

    return applied


def command_hints(report: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    priority = report.get("env_priority") or {}
    if priority.get("p0_vault"):
        hints.append("pnpm vault:dev:up && pnpm vault:dev:seed  # lokal")
        hints.append("pnpm vault:verify:tenant  # nach Vault-Setup")
    if priority.get("p1_gateway"):
        hints.append(
            "python scripts/mint_dashboard_gateway_jwt.py "
            f"--env-file {Path(report['env_file']).name} --update-env-file"
        )
    hints.append("pnpm go-live:trade-ready:strict  # erneut pruefen")
    return hints


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    ap.add_argument("--strict-runtime", action="store_true")
    ap.add_argument("--skip-audit", action="store_true")
    ap.add_argument(
        "--apply-safe",
        action="store_true",
        help="Nur sichere Auto-Fixes (JWT mint, REDIS_PASSWORD, optional vault-dev).",
    )
    ap.add_argument(
        "--vault-dev",
        action="store_true",
        help="Mit --apply-safe: VAULT_* aus .env.vault-dev.example mergen.",
    )
    args = ap.parse_args()

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}", file=sys.stderr)
        return 2

    if args.apply_safe:
        backup = args.env_file.with_suffix(args.env_file.suffix + ".backup")
        if not backup.is_file():
            backup.write_text(
                args.env_file.read_text(encoding="utf-8"), encoding="utf-8"
            )
            print(f"Backup: {backup.name}")
        fixes = apply_safe_fixes(args.env_file, vault_dev=args.vault_dev)
        if fixes:
            print("Angewendet (keine Secret-Werte geloggt):")
            for item in fixes:
                print(f"  - {item}")
        else:
            print("Keine sicheren Auto-Fixes moeglich.")

    trade = _load_trade_ready()
    report = trade.evaluate_trade_ready(
        env_file=args.env_file,
        strict_runtime=args.strict_runtime,
        skip_audit=args.skip_audit,
    )
    trade._print_human(report)

    if not report.get("trade_ready"):
        print("\nBefehle:")
        for cmd in command_hints(report):
            print(f"  {cmd}")

    if args.strict_runtime:
        return 0 if report.get("trade_ready") else 1
    return 0 if report.get("code_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
