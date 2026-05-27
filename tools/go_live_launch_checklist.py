#!/usr/bin/env python3
"""
Go-Live Launch-Checklist: ein Einstiegspunkt vor LIVE-Trading.

Fuehrt repo-seitige Checks aus (ENV, Ops-Preflight, Readiness-Audit) und listet
externe Ops-Schritte (IdP, Vault, Bitget, Shadow-Burn-in). Gibt keine Secrets aus.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StepResult:
    id: str
    label: str
    ok: bool
    exit_code: int
    detail: str


def _run_step(
    step_id: str,
    label: str,
    argv: list[str],
    *,
    cwd: Path = ROOT,
) -> StepResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return StepResult(
            id=step_id,
            label=label,
            ok=False,
            exit_code=127,
            detail=str(exc)[:500],
        )
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = tail[-1] if tail else f"exit={proc.returncode}"
    return StepResult(
        id=step_id,
        label=label,
        ok=proc.returncode == 0,
        exit_code=int(proc.returncode),
        detail=detail[:500],
    )


def _load_env_keys(path: Path) -> dict[str, str]:
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


def _is_placeholder_value(val: str) -> bool:
    s = (val or "").strip()
    if not s:
        return True
    u = s.upper()
    if s.startswith("<") and s.endswith(">"):
        return True
    if u.startswith("YOUR_") or u in ("SET_ME", "CHANGE_ME"):
        return True
    if "SET_OPERATOR" in u or "SET_ME" in u:
        return True
    return False


def run_launch_checklist(
    *,
    env_file: Path,
    strict_runtime: bool,
    skip_audit: bool,
) -> tuple[list[StepResult], list[str]]:
    py = sys.executable
    env_arg = str(env_file.resolve())
    template_flag = [] if strict_runtime else ["--template"]
    strict_flag = ["--strict-runtime"] if strict_runtime else []
    env_keys = _load_env_keys(env_file)

    steps: list[StepResult] = []

    steps.append(
        _run_step(
            "env_10_10",
            "ENV 10/10 Safety",
            [
                py,
                str(ROOT / "tools" / "check_env_10_10_safety.py"),
                "--env-file",
                env_arg,
                "--profile",
                "production",
                *template_flag,
                *(["--strict-runtime"] if strict_runtime else []),
            ],
        )
    )
    steps.append(
        _run_step(
            "go_live_ops",
            "Go-Live Ops Preflight",
            [
                py,
                str(ROOT / "tools" / "go_live_ops_preflight.py"),
                "--env-file",
                env_arg,
                *strict_flag,
            ],
        )
    )

    vault_on = env_keys.get("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "").lower() in (
        "true",
        "1",
        "yes",
    )
    tenant_id = (
        env_keys.get("MODUL_MATE_GATE_TENANT_ID")
        or env_keys.get("COMMERCIAL_DEFAULT_TENANT_ID")
        or ""
    ).strip()
    if strict_runtime and vault_on and not _is_placeholder_value(tenant_id):
        vault_argv = [
            py,
            str(ROOT / "tools" / "verify_vault_tenant_credentials.py"),
            "--env-file",
            env_arg,
            "--tenant-id",
            tenant_id,
        ]
        steps.append(
            _run_step(
                "vault_tenant_credentials",
                "Vault Tenant Credentials",
                vault_argv,
            )
        )

    if not skip_audit:
        audit_argv = [py, str(ROOT / "tools" / "production_readiness_audit.py")]
        if strict_runtime:
            audit_argv.append("--strict")
        steps.append(
            _run_step(
                "readiness_audit",
                "Production Readiness Audit",
                audit_argv,
            )
        )

    external: list[str] = [
        "IdP: PORTAL_AUTH_PROVIDER=oidc, Smoke-Login /api/auth/callback",
        "Vault: python tools/verify_vault_tenant_credentials.py --env-file .env.production --tenant-id <TENANT>",
        "Bitget: python tools/verify_bitget_rest.py live-readonly --tenant-id <TENANT>",
        "Portal Go-Live: POST /v1/commerce/customer/live-execution/enable",
        "Shadow-Burn-in: python scripts/verify_shadow_burn_in.py --hours 72 --strict",
        "Erst danach: LIVE_TRADE_ENABLE=true + Operator-Freigabe",
    ]
    return steps, external


def build_summary(
    steps: list[StepResult],
    external: list[str],
    *,
    strict_runtime: bool,
    env_file: Path,
) -> dict[str, Any]:
    repo_ok = all(s.ok for s in steps)
    return {
        "ok": repo_ok,
        "strict_runtime": strict_runtime,
        "env_file": str(env_file),
        "repo_checks_ok": repo_ok,
        "external_ops_required": True,
        "steps": [asdict(s) for s in steps],
        "external_next": external,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.production.example",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="Echte .env.production ohne Platzhalter (Pflicht vor LIVE).",
    )
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}", file=sys.stderr)
        return 2

    steps, external = run_launch_checklist(
        env_file=args.env_file,
        strict_runtime=args.strict_runtime,
        skip_audit=args.skip_audit,
    )
    summary = build_summary(
        steps,
        external,
        strict_runtime=args.strict_runtime,
        env_file=args.env_file,
    )

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        mode = "strict-runtime" if args.strict_runtime else "template"
        print(f"go-live launch checklist ({mode}): {args.env_file.name}")
        for step in steps:
            status = "PASS" if step.ok else "FAIL"
            print(f"  [{status}] {step.label}: {step.detail}")
        print("\nExterne Ops (nicht automatisierbar):")
        for item in external:
            print(f"  - {item}")
        print(
            f"\nRepo-Checks: {'PASS' if summary['repo_checks_ok'] else 'FAIL'} "
            f"(strict={args.strict_runtime})"
        )

    if not summary["repo_checks_ok"]:
        if not args.json:
            print("\nFehlerbehebung (haeufig):", file=sys.stderr)
            for step in steps:
                if not step.ok:
                    print(f"  - {step.id}: {step.detail}", file=sys.stderr)
            if args.strict_runtime:
                print(
                    "  - VAULT_TOKEN: echten Token aus Vault setzen (nicht YOUR_*_HERE)",
                    file=sys.stderr,
                )
                print(
                    "  - Vault-Pfad: python tools/verify_vault_tenant_credentials.py "
                    "--env-file .env.production --tenant-id <TENANT>",
                    file=sys.stderr,
                )
                print(
                    "  - OIDC_* / GATEWAY_*: alle Platzhalter in .env.production ersetzen",
                    file=sys.stderr,
                )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
