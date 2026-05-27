#!/usr/bin/env python3
"""
Go-Live Ops-Preflight: prueft ENV-Konsistenz vor LIVE-Trading (ohne Secrets auszugeben).

Fokus: OIDC, Vault-Tenant-Credentials, Go-Live-Gates, Commercial-Gates, Manual-Action.
Optional --strict-runtime: Platzhalter in Pflicht-Keys sind Fehler.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_MARKERS = (
    "<set_me>",
    "<changeme>",
    "your_api_key_here",
    "your_secret_value_here",
    "your_value_here",
    "your_base32_totp_secret_here",
    "your_oidc_client_id",
    "<set_operator_tenant_id>",
    "<set_operator_live_allowlist_symbols>",
)

BOOL_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PreflightIssue:
    severity: str  # error | warning
    code: str
    key: str | None
    message: str


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        env[key] = value
    return env


def truthy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in BOOL_TRUE


def is_placeholder(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    lower = v.lower()
    if lower.startswith("<") and lower.endswith(">"):
        return True
    return any(marker in lower for marker in PLACEHOLDER_MARKERS)


def _issue(
    issues: list[PreflightIssue],
    *,
    severity: str,
    code: str,
    message: str,
    key: str | None = None,
) -> None:
    issues.append(PreflightIssue(severity=severity, code=code, key=key, message=message))


def _require_present(
    issues: list[PreflightIssue],
    env: dict[str, str],
    key: str,
    *,
    code: str,
    strict_runtime: bool,
) -> None:
    val = env.get(key, "").strip()
    if not val:
        _issue(
            issues,
            severity="error",
            code=code,
            key=key,
            message=f"Pflicht-ENV fehlt oder leer: {key}",
        )
        return
    if strict_runtime and is_placeholder(val):
        _issue(
            issues,
            severity="error",
            code=f"{code}_placeholder",
            key=key,
            message=f"Pflicht-ENV ist Platzhalter: {key}",
        )


def _redirect_matches_frontend(redirect: str, frontend: str) -> bool:
    r = urlparse(redirect.strip())
    f = urlparse(frontend.strip())
    if not r.scheme or not r.netloc or not f.scheme or not f.netloc:
        return False
    expected_path = "/api/auth/callback"
    return (
        r.scheme == f.scheme
        and r.netloc == f.netloc
        and r.path.rstrip("/") == expected_path
    )


def evaluate_go_live_preflight(
    env: dict[str, str],
    *,
    strict_runtime: bool = False,
) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    production = truthy(env, "PRODUCTION") or env.get("APP_ENV", "").lower() == "production"
    live_trade = truthy(env, "LIVE_TRADE_ENABLE")
    vault_tenant = truthy(env, "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT")
    oidc = env.get("PORTAL_AUTH_PROVIDER", "mock").strip().lower() == "oidc"

    if production and env.get("PORTAL_AUTH_PROVIDER", "").strip().lower() == "mock":
        _issue(
            issues,
            severity="error",
            code="production_mock_login_forbidden",
            key="PORTAL_AUTH_PROVIDER",
            message="Production erfordert PORTAL_AUTH_PROVIDER=oidc (Mock ist Dev-only).",
        )

    if oidc:
        for key in (
            "OIDC_ISSUER",
            "OIDC_CLIENT_ID",
            "OIDC_CLIENT_SECRET",
            "OIDC_REDIRECT_URI",
            "OIDC_DEFAULT_TENANT_ID",
        ):
            _require_present(
                issues,
                env,
                key,
                code="oidc_incomplete",
                strict_runtime=strict_runtime,
            )
        redirect = env.get("OIDC_REDIRECT_URI", "")
        frontend = env.get("FRONTEND_URL", "")
        if redirect and frontend and not _redirect_matches_frontend(redirect, frontend):
            _issue(
                issues,
                severity="error",
                code="oidc_redirect_frontend_mismatch",
                key="OIDC_REDIRECT_URI",
                message=(
                    "OIDC_REDIRECT_URI muss {FRONTEND_URL}/api/auth/callback entsprechen."
                ),
            )

    if truthy(env, "GO_LIVE_REQUIRE_STEP_UP"):
        _require_present(
            issues,
            env,
            "GO_LIVE_STEP_UP_TOTP_SECRET",
            code="go_live_step_up_missing",
            strict_runtime=strict_runtime,
        )
        if env.get("GO_LIVE_STEP_UP_PIN", "").strip():
            _issue(
                issues,
                severity="error",
                code="go_live_pin_forbidden_in_production",
                key="GO_LIVE_STEP_UP_PIN",
                message="GO_LIVE_STEP_UP_PIN ist in Production unzulaessig.",
            )

    if vault_tenant:
        _require_present(
            issues,
            env,
            "VAULT_ADDR",
            code="vault_addr_missing",
            strict_runtime=strict_runtime,
        )
        _require_present(
            issues,
            env,
            "MODUL_MATE_GATE_TENANT_ID",
            code="modul_mate_tenant_missing",
            strict_runtime=strict_runtime,
        )
        if not truthy(env, "VAULT_HYDRATE_ON_BOOT"):
            _issue(
                issues,
                severity="warning",
                code="vault_hydrate_disabled",
                key="VAULT_HYDRATE_ON_BOOT",
                message=(
                    "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true: "
                    "VAULT_HYDRATE_ON_BOOT=true empfohlen."
                ),
            )
        for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"):
            if env.get(key, "").strip() and strict_runtime:
                _issue(
                    issues,
                    severity="warning",
                    code="global_bitget_keys_with_vault_tenant",
                    key=key,
                    message=(
                        "Bei Vault-Tenant-Credentials sollten globale BITGET_* "
                        "in Runtime leer sein (nur Vault-Pfad bitget/{tenant}/live)."
                    ),
                )

    if truthy(env, "GATEWAY_ENFORCE_SENSITIVE_AUTH") and truthy(
        env, "GATEWAY_MANUAL_ACTION_REQUIRED"
    ):
        _require_present(
            issues,
            env,
            "GATEWAY_MANUAL_ACTION_SECRET",
            code="manual_action_secret_missing",
            strict_runtime=strict_runtime,
        )

    if live_trade:
        for key in (
            "COMMERCIAL_ENABLED",
            "COMMERCIAL_ENTITLEMENT_ENFORCE",
            "COMMERCIAL_REQUIRE_CONTRACT_FOR_LIVE",
        ):
            if not truthy(env, key):
                _issue(
                    issues,
                    severity="error",
                    code="live_trade_commercial_gates",
                    key=key,
                    message=f"LIVE_TRADE_ENABLE=true erfordert {key}=true.",
                )
        if not any(
            truthy(env, k)
            for k in (
                "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL",
                "GATEWAY_MANUAL_ACTION_REQUIRED",
            )
            if k in env
        ):
            _issue(
                issues,
                severity="error",
                code="live_trade_safety_support_missing",
                key="GATEWAY_MANUAL_ACTION_REQUIRED",
                message=(
                    "LIVE_TRADE_ENABLE=true erfordert Safety-Latch oder Manual-Action-Gate."
                ),
            )

    cooldown = env.get("GO_LIVE_COOLDOWN_SEC", "").strip()
    if cooldown:
        try:
            if int(cooldown) < 300:
                _issue(
                    issues,
                    severity="warning",
                    code="go_live_cooldown_short",
                    key="GO_LIVE_COOLDOWN_SEC",
                    message="GO_LIVE_COOLDOWN_SEC < 300s ist fuer Production sehr kurz.",
                )
        except ValueError:
            _issue(
                issues,
                severity="error",
                code="go_live_cooldown_invalid",
                key="GO_LIVE_COOLDOWN_SEC",
                message="GO_LIVE_COOLDOWN_SEC muss eine Ganzzahl sein.",
            )

    if truthy(env, "GATEWAY_MOCK_BITGET_VERIFY") and production:
        _issue(
            issues,
            severity="error",
            code="mock_bitget_verify_in_production",
            key="GATEWAY_MOCK_BITGET_VERIFY",
            message="GATEWAY_MOCK_BITGET_VERIFY=true ist in Production verboten.",
        )

    modul_tid = env.get("MODUL_MATE_GATE_TENANT_ID", "").strip()
    commercial_tid = env.get("COMMERCIAL_DEFAULT_TENANT_ID", "").strip()
    oidc_tid = env.get("OIDC_DEFAULT_TENANT_ID", "").strip()
    if modul_tid and commercial_tid and modul_tid != commercial_tid:
        _issue(
            issues,
            severity="warning",
            code="tenant_id_mismatch",
            key="MODUL_MATE_GATE_TENANT_ID",
            message=(
                "MODUL_MATE_GATE_TENANT_ID und COMMERCIAL_DEFAULT_TENANT_ID "
                "sollten uebereinstimmen."
            ),
        )
    if oidc and oidc_tid and commercial_tid and oidc_tid != commercial_tid:
        _issue(
            issues,
            severity="warning",
            code="oidc_tenant_mismatch",
            key="OIDC_DEFAULT_TENANT_ID",
            message="OIDC_DEFAULT_TENANT_ID sollte COMMERCIAL_DEFAULT_TENANT_ID entsprechen.",
        )

    return issues


def build_summary(
    env: dict[str, str],
    issues: list[PreflightIssue],
    *,
    strict_runtime: bool,
) -> dict[str, Any]:
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "ok": not errors,
        "strict_runtime": strict_runtime,
        "key_count": len(env),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(i) for i in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.production.example",
        help="ENV-Datei (Default: .env.production.example als Template-Check)",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="Platzhalter in Pflicht-Keys als Fehler (echte Production-Datei).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}", file=sys.stderr)
        return 2

    env = load_dotenv(args.env_file)
    issues = evaluate_go_live_preflight(env, strict_runtime=args.strict_runtime)
    summary = build_summary(env, issues, strict_runtime=args.strict_runtime)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        mode = "strict-runtime" if args.strict_runtime else "template"
        print(f"go-live ops preflight ({mode}): {args.env_file.name}")
        for issue in issues:
            key = f" [{issue.key}]" if issue.key else ""
            print(f"  {issue.severity.upper()} {issue.code}{key}: {issue.message}")
        print(
            f"Result: {'PASS' if summary['ok'] else 'FAIL'} "
            f"(errors={summary['error_count']} warnings={summary['warning_count']})"
        )

    if not summary["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
