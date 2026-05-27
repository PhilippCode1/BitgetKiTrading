#!/usr/bin/env python3
"""
Go-Live Trade-Ready: eine GO/NO-GO-Matrix vor echtem LIVE-Trading.

Fuehrt repo-seitige Checks aus (Launch-Checklist) und listet Ops-Blocker
ohne Secret-Werte. Kein Ersatz fuer Vault/Bitget/Burn-in — aber ein
einziger Einstiegspunkt fuer Operatoren.

Beispiele:
  python tools/go_live_trade_ready.py
  python tools/go_live_trade_ready.py --env-file .env.production --strict-runtime
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Prioritaet fuer Ops-Blocker (Namen only — keine Werte loggen).
_P0_VAULT = frozenset(
    {"VAULT_TOKEN", "VAULT_SECRET_ID", "VAULT_ADDR", "VAULT_ROLE_ID", "VAULT_KV_MOUNT"}
)
_P0_TENANT = frozenset(
    {
        "MODUL_MATE_GATE_TENANT_ID",
        "COMMERCIAL_DEFAULT_TENANT_ID",
        "OIDC_DEFAULT_TENANT_ID",
    }
)
_P1_OIDC = frozenset(
    {
        "PORTAL_AUTH_PROVIDER",
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_REDIRECT_URI",
    }
)
_P1_GATEWAY = frozenset(
    {
        "DASHBOARD_GATEWAY_AUTHORIZATION",
        "GATEWAY_JWT_SECRET",
        "INTERNAL_API_KEY",
        "GATEWAY_MANUAL_ACTION_SECRET",
    }
)
_P2_INFRA = frozenset({"REDIS_PASSWORD", "DATABASE_URL"})


def prioritize_env_keys(keys: list[str]) -> dict[str, list[str]]:
    """Gruppiert fehlende/Platzhalter-Keys nach Ops-Prioritaet."""
    groups: dict[str, list[str]] = {
        "p0_vault": [],
        "p0_tenant": [],
        "p1_oidc_portal": [],
        "p1_gateway": [],
        "p2_infra": [],
        "other": [],
    }
    for key in sorted(set(keys)):
        if key in _P0_VAULT:
            groups["p0_vault"].append(key)
        elif key in _P0_TENANT:
            groups["p0_tenant"].append(key)
        elif key in _P1_OIDC:
            groups["p1_oidc_portal"].append(key)
        elif key in _P1_GATEWAY:
            groups["p1_gateway"].append(key)
        elif key in _P2_INFRA:
            groups["p2_infra"].append(key)
        else:
            groups["other"].append(key)
    return {k: v for k, v in groups.items() if v}


def remediation_steps(priority: dict[str, list[str]]) -> list[str]:
    steps: list[str] = []
    if priority.get("p0_vault"):
        steps.append(
            "P0 Vault: VAULT_TOKEN/ADDR setzen; Secrets unter bitget/{tenant_id}/live "
            "(pnpm vault:verify:tenant). Lokal: pnpm vault:dev:up && pnpm vault:dev:seed"
        )
    if priority.get("p0_tenant"):
        steps.append(
            "P0 Tenant: MODUL_MATE_GATE_TENANT_ID und COMMERCIAL_DEFAULT_TENANT_ID "
            "auf echte Mandanten-UUID setzen (kein <SET_…>)."
        )
    if priority.get("p1_oidc_portal"):
        steps.append(
            "P1 IdP: OIDC_* + PORTAL_AUTH_PROVIDER=oidc; Smoke-Login /api/auth/callback."
        )
    if priority.get("p1_gateway"):
        steps.append(
            "P1 Gateway/Dashboard: JWT/Internal-Keys und DASHBOARD_GATEWAY_AUTHORIZATION minten."
        )
    if priority.get("p2_infra"):
        steps.append("P2 Infra: REDIS/DATABASE-Credentials fuer Production setzen.")
    if priority.get("other"):
        steps.append(
            "Weitere Platzhalter in .env.production ersetzen: "
            + ", ".join(priority["other"][:8])
            + ("…" if len(priority["other"]) > 8 else "")
        )
    steps.extend(
        [
            "Bitget: python tools/verify_bitget_rest.py live-readonly --tenant-id <TENANT>",
            "Shadow: python scripts/verify_shadow_burn_in.py --hours 72 --strict",
            "Portal Go-Live, dann LIVE_TRADE_ENABLE=true + Operator-Freigabe",
        ]
    )
    return steps


def _load_checklist_module():
    path = ROOT / "tools" / "go_live_launch_checklist.py"
    name = "go_live_launch_checklist"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_env_checker():
    path = ROOT / "tools" / "check_env_10_10_safety.py"
    name = "check_env_10_10_safety"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def evaluate_trade_ready(
    *,
    env_file: Path,
    strict_runtime: bool,
    skip_audit: bool,
) -> dict[str, Any]:
    checklist = _load_checklist_module()
    steps, external = checklist.run_launch_checklist(
        env_file=env_file,
        strict_runtime=strict_runtime,
        skip_audit=skip_audit,
    )
    repo_ok = all(s.ok for s in steps)
    failing_steps = [
        {"id": s.id, "label": s.label, "detail": s.detail}
        for s in steps
        if not s.ok
    ]

    env_issues: list[dict[str, str]] = []
    if strict_runtime:
        env_mod = _load_env_checker()
        env = env_mod.load_dotenv(env_file)
        issues = env_mod.validate_env(
            env,
            profile="production",
            template=False,
            strict_runtime=True,
        )
        env_issues = [
            {
                "severity": i.severity,
                "code": i.code,
                "key": i.key or "",
                "message": i.message,
            }
            for i in issues
            if i.severity == "error"
        ]

    env_config_steps = [s for s in steps if s.id != "vault_tenant_credentials"]
    vault_step = next((s for s in steps if s.id == "vault_tenant_credentials"), None)
    env_config_ready = all(s.ok for s in env_config_steps) if strict_runtime else None
    vault_runtime_ready = (
        vault_step.ok if vault_step is not None else None
    )

    code_template_steps, _ = checklist.run_launch_checklist(
        env_file=ROOT / ".env.production.example",
        strict_runtime=False,
        skip_audit=True,
    )
    code_ready = all(s.ok for s in code_template_steps)

    ops_ready = repo_ok if strict_runtime else None
    trade_ready = code_ready and bool(ops_ready) if strict_runtime else False

    env_keys = sorted({e["key"] for e in env_issues if e.get("key")})
    env_priority = prioritize_env_keys(env_keys) if env_keys else {}
    remediation = remediation_steps(env_priority) if env_priority else []

    return {
        "trade_ready": trade_ready,
        "code_ready": code_ready,
        "ops_ready": ops_ready,
        "env_config_ready": env_config_ready,
        "vault_runtime_ready": vault_runtime_ready,
        "strict_runtime": strict_runtime,
        "env_file": str(env_file),
        "failing_steps": failing_steps,
        "env_errors": env_issues,
        "env_keys_missing": env_keys,
        "env_priority": env_priority,
        "remediation": remediation,
        "external_ops": external,
        "steps": [
            {"id": s.id, "ok": s.ok, "label": s.label, "detail": s.detail}
            for s in steps
        ],
    }


def _print_human(report: dict[str, Any]) -> None:
    mode = "strict" if report["strict_runtime"] else "template"
    print(f"Go-Live Trade-Ready ({mode}): {Path(report['env_file']).name}")
    print()
    print("| Bereich | Status |")
    print("|---|---|")
    code = "GO" if report["code_ready"] else "NO-GO"
    print(f"| Code (Template-Checks) | {code} |")
    if report["strict_runtime"]:
        env_cfg = "GO" if report.get("env_config_ready") else "NO-GO"
        print(f"| ENV-Konfiguration (.env strict) | {env_cfg} |")
        vault_rt = report.get("vault_runtime_ready")
        if vault_rt is not None:
            print(
                f"| Vault-Runtime (Tenant-Secret erreichbar) | "
                f"{'GO' if vault_rt else 'NO-GO'} |"
            )
        ops = "GO" if report["ops_ready"] else "NO-GO"
        print(f"| Ops gesamt | {ops} |")
        overall = "GO" if report["trade_ready"] else "NO-GO"
        print(f"| **Echtgeld-Trading** | **{overall}** |")
    else:
        print("| Ops (.env.production) | (mit --strict-runtime pruefen) |")
        print("| **Echtgeld-Trading** | **NO-GO** (Strict-Modus fehlt) |")

    if report["failing_steps"]:
        print("\nFehlgeschlagene Repo-Checks:")
        for step in report["failing_steps"]:
            print(f"  - {step['id']}: {step['detail']}")

    if report["env_errors"]:
        keys = report.get("env_keys_missing") or sorted(
            {e["key"] for e in report["env_errors"] if e.get("key")}
        )
        priority = report.get("env_priority") or {}
        if priority:
            print("\nENV-Platzhalter nach Prioritaet (Namen only):")
            labels = {
                "p0_vault": "P0 Vault (Hard No-Go)",
                "p0_tenant": "P0 Mandant",
                "p1_oidc_portal": "P1 IdP/Portal",
                "p1_gateway": "P1 Gateway/Dashboard",
                "p2_infra": "P2 Infra",
                "other": "Sonstige",
            }
            for group, label in labels.items():
                group_keys = priority.get(group) or []
                if group_keys:
                    print(f"  {label}: {', '.join(group_keys)}")
        elif keys:
            print("\nENV-Keys mit Platzhalter/leer (Namen only, keine Werte):")
            for key in keys:
                print(f"  - {key}")

    remediation = report.get("remediation") or []
    if remediation and not report["trade_ready"]:
        print("\nEmpfohlene Reihenfolge:")
        for idx, step in enumerate(remediation, start=1):
            print(f"  {idx}. {step}")

    print("\nExterne Ops (manuell, vor LIVE_TRADE_ENABLE=true):")
    for item in report["external_ops"]:
        print(f"  [ ] {item}")

    if not report["trade_ready"]:
        if report.get("env_config_ready") and report.get("vault_runtime_ready") is False:
            print(
                "\nNaechster Schritt: Docker Desktop starten, dann:\n"
                "  pnpm vault:dev:up && pnpm vault:dev:seed && pnpm go-live:trade-ready:strict"
            )
        else:
            print(
                "\nNaechster Schritt: Platzhalter in .env.production ersetzen, dann:\n"
                "  pnpm go-live:trade-ready:strict"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.production",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="Echte Production-ENV pruefen (Pflicht vor LIVE).",
    )
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}", file=sys.stderr)
        return 2

    report = evaluate_trade_ready(
        env_file=args.env_file,
        strict_runtime=args.strict_runtime,
        skip_audit=args.skip_audit,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    if args.strict_runtime:
        return 0 if report["trade_ready"] else 1
    return 0 if report["code_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
