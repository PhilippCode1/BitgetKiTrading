#!/usr/bin/env python3
"""Static 10/10 ENV safety checker for bitget-btc-ai.

The checker never prints raw ENV values. It validates key names, boolean
combinations, required presence, placeholders, browser exposure, and live-mode
gates for local/shadow/production profiles.
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
REQUIRED_MATRIX = ROOT / "config" / "required_secrets_matrix.json"

STATUS_ERROR = "error"
STATUS_WARNING = "warning"

BOOL_TRUE = {"1", "true", "yes", "on"}
BOOL_FALSE = {"0", "false", "no", "off"}
PROFILES = {"local", "shadow", "production", "test", "staging"}

PLACEHOLDER_MARKERS = (
    "<set_me>",
    "<changeme>",
    "changeme",
    "change_me",
    "set_me",
    "your_api_key_here",
    "your_secret_value_here",
    "your_value_here",
    "your_bearer_jwt",
    "placeholder",
    "example_only",
    "replace_me",
)

SECRET_NAME_FRAGMENTS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSPHRASE",
    "API_KEY",
    "JWT",
    "AUTHORIZATION",
    "ENCRYPTION_KEY",
)

BROWSER_FORBIDDEN_FRAGMENTS = (
    "OPENAI",
    "BITGET",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSPHRASE",
    "API_KEY",
    "JWT",
    "ENCRYPTION",
    "INTERNAL",
    "DASHBOARD_GATEWAY",
    "ADMIN_TOKEN",
    "TELEGRAM_BOT",
    "TELEGRAM_WEBHOOK",
    "STRIPE",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[0-9a-zA-Z]{20,}"),
    re.compile(r"sk-(?:proj|test|live)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


@dataclass(frozen=True)
class EnvIssue:
    severity: str
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
        value = _strip_inline_comment(value.strip())
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        env[key] = value
    return env


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    out: list[str] = []
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or value[i - 1].isspace():
                break
        out.append(ch)
    return "".join(out).strip()


def truthy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in BOOL_TRUE


def falsy(env: dict[str, str], key: str) -> bool:
    raw = env.get(key, "").strip().lower()
    return raw in BOOL_FALSE or raw == ""


def is_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    if lower.startswith("bearer "):
        lower = lower[7:].strip()
    if lower.startswith("<") and lower.endswith(">"):
        return True
    return any(marker in lower for marker in PLACEHOLDER_MARKERS)


def is_secretish_key(key: str) -> bool:
    upper = key.upper()
    return any(fragment in upper for fragment in SECRET_NAME_FRAGMENTS)


def required_keys_for_profile(profile: str) -> set[str]:
    if not REQUIRED_MATRIX.is_file():
        return set()
    data = json.loads(REQUIRED_MATRIX.read_text(encoding="utf-8"))
    matrix_profile = "staging" if profile == "shadow" else profile
    required: set[str] = set()
    for entry in data.get("entries", []):
        if entry.get(matrix_profile) == "required":
            env_name = str(entry.get("env", "")).strip()
            if env_name:
                required.add(env_name)
    return required


def _is_prod_like(env: dict[str, str], profile: str) -> bool:
    return profile == "production" or truthy(env, "PRODUCTION") or env.get("APP_ENV") == "production"


def _is_shadow_like(env: dict[str, str], profile: str) -> bool:
    return (
        profile == "shadow"
        or env.get("APP_ENV") == "shadow"
        or env.get("EXECUTION_MODE") == "shadow"
    )


def _has_loopback(value: str) -> bool:
    if not value.strip():
        return False
    parts = [p.strip() for p in value.split(",") if p.strip()]
    for part in parts or [value]:
        parsed = urlparse(part)
        host = parsed.hostname or ""
        if host.lower() in {"localhost", "127.0.0.1", "::1"}:
            return True
        if part.lower().startswith(("http://localhost", "https://localhost")):
            return True
    return False


def _actual_secret_value_present(env: dict[str, str], key: str) -> bool:
    value = env.get(key, "")
    return bool(value.strip()) and not is_placeholder(value)


def _issue(
    issues: list[EnvIssue],
    code: str,
    message: str,
    key: str | None = None,
    severity: str = STATUS_ERROR,
) -> None:
    issues.append(EnvIssue(severity=severity, code=code, key=key, message=message))


def validate_env(
    env: dict[str, str],
    *,
    profile: str,
    template: bool = False,
    strict_runtime: bool = False,
) -> list[EnvIssue]:
    issues: list[EnvIssue] = []
    prod_like = _is_prod_like(env, profile)
    shadow_like = _is_shadow_like(env, profile)

    expected_app_env = {"production": "production", "shadow": "shadow", "local": "local"}.get(
        profile
    )
    if expected_app_env and env.get("APP_ENV") and env.get("APP_ENV") != expected_app_env:
        _issue(
            issues,
            "profile_app_env_mismatch",
            f"profile={profile} expects APP_ENV={expected_app_env}.",
            "APP_ENV",
        )

    for key in required_keys_for_profile(profile):
        if key not in env:
            _issue(issues, "missing_required_key", "required key is absent.", key)
        elif strict_runtime and is_placeholder(env.get(key, "")):
            _issue(issues, "placeholder_required_secret", "required runtime value is blank or placeholder.", key)

    for key, value in sorted(env.items()):
        key_u = key.upper()
        if key_u.startswith("NEXT_PUBLIC_"):
            if any(fragment in key_u for fragment in BROWSER_FORBIDDEN_FRAGMENTS):
                _issue(
                    issues,
                    "browser_secret_key_name",
                    "NEXT_PUBLIC_* must not expose secret-like names.",
                    key,
                )
            if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
                _issue(
                    issues,
                    "browser_secret_value",
                    "NEXT_PUBLIC_* value looks like a raw secret.",
                    key,
                )
        if strict_runtime and is_secretish_key(key) and is_placeholder(value):
            _issue(issues, "placeholder_runtime_secret", "runtime secret is blank or placeholder.", key)

    if prod_like:
        forbidden_true = (
            "DEBUG",
            "LLM_USE_FAKE_PROVIDER",
            "NEWS_FIXTURE_MODE",
            "BITGET_DEMO_ENABLED",
            "BITGET_RELAX_CREDENTIAL_ISOLATION",
        )
        for key in forbidden_true:
            if truthy(env, key):
                _issue(issues, "production_forbidden_true", "value must not be true in production.", key)

        for key, value in env.items():
            if key.endswith("_URL") or key in {
                "API_GATEWAY_URL",
                "NEXT_PUBLIC_API_BASE_URL",
                "NEXT_PUBLIC_WS_BASE_URL",
                "DATABASE_URL",
                "DATABASE_URL_DOCKER",
                "REDIS_URL",
                "REDIS_URL_DOCKER",
                "CORS_ALLOW_ORIGINS",
                "APP_BASE_URL",
                "FRONTEND_URL",
            }:
                if _has_loopback(value):
                    _issue(issues, "production_loopback_url", "loopback URL is forbidden in production runtime.", key)

    if shadow_like and truthy(env, "LIVE_TRADE_ENABLE"):
        _issue(issues, "shadow_live_trade_enabled", "shadow mode must not enable live order submission.", "LIVE_TRADE_ENABLE")

    if profile == "local":
        if truthy(env, "LLM_USE_FAKE_PROVIDER") or truthy(env, "BITGET_DEMO_ENABLED"):
            _issue(
                issues,
                "local_not_production_ready",
                "local profile may use fake/demo providers but is not production-ready.",
                None,
                severity=STATUS_WARNING,
            )

    if truthy(env, "LIVE_TRADE_ENABLE"):
        required_true = (
            ("EXECUTION_MODE", "live", "live_trade_requires_live_execution_mode"),
            ("LIVE_BROKER_ENABLED", "true", "live_trade_requires_live_broker"),
            (
                "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN",
                "true",
                "live_trade_requires_operator_release",
            ),
            (
                "REQUIRE_SHADOW_MATCH_BEFORE_LIVE",
                "true",
                "live_trade_requires_shadow_match",
            ),
            (
                "LIVE_REQUIRE_EXCHANGE_HEALTH",
                "true",
                "live_trade_requires_exchange_health",
            ),
            ("RISK_HARD_GATING_ENABLED", "true", "live_trade_requires_risk_governor"),
            ("LIVE_KILL_SWITCH_ENABLED", "true", "live_trade_requires_kill_switch"),
        )
        for key, expected, code in required_true:
            actual = env.get(key, "")
            ok = actual == expected if key == "EXECUTION_MODE" else truthy(env, key)
            if not ok:
                _issue(issues, code, f"LIVE_TRADE_ENABLE=true requires {key}={expected}.", key)

        if not (
            truthy(env, "COMMERCIAL_ENABLED")
            and truthy(env, "COMMERCIAL_ENTITLEMENT_ENFORCE")
            and truthy(env, "COMMERCIAL_REQUIRE_CONTRACT_FOR_LIVE")
        ):
            _issue(
                issues,
                "live_trade_requires_commercial_tenant_gates",
                "LIVE_TRADE_ENABLE=true requires commercial, entitlement, and tenant contract gates.",
                "COMMERCIAL_ENABLED",
            )

        safety_keys = (
            "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL",
            "GATEWAY_MANUAL_ACTION_REQUIRED",
            "GATEWAY_REQUIRE_MANUAL_ACTION_TOKEN",
        )
        if not any(truthy(env, key) for key in safety_keys if key in env):
            _issue(
                issues,
                "live_trade_requires_safety_latch_support",
                "LIVE_TRADE_ENABLE=true requires explicit safety-latch/manual-action support.",
                "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL",
            )

    demo_enabled = truthy(env, "BITGET_DEMO_ENABLED")
    live_keys = any(
        _actual_secret_value_present(env, key)
        for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE")
    )
    demo_keys = any(
        _actual_secret_value_present(env, key)
        for key in (
            "BITGET_DEMO_API_KEY",
            "BITGET_DEMO_API_SECRET",
            "BITGET_DEMO_API_PASSPHRASE",
        )
    )
    if demo_enabled and live_keys:
        _issue(
            issues,
            "bitget_demo_live_key_mix",
            "BITGET_DEMO_ENABLED=true must not be combined with live Bitget credential names.",
            "BITGET_DEMO_ENABLED",
        )
    if live_keys and demo_keys:
        _issue(
            issues,
            "bitget_demo_live_key_mix",
            "Demo and live Bitget credential sets must not be present together.",
            "BITGET_API_KEY",
        )

    if strict_runtime and template:
        _issue(issues, "mode_conflict", "--template and --strict-runtime are mutually exclusive.")

    if template:
        # Template placeholders are allowed for server-side secrets, but missing
        # required key names and dangerous booleans are still errors.
        issues = [
            issue
            for issue in issues
            if issue.code
            not in {
                "placeholder_required_secret",
                "placeholder_runtime_secret",
            }
        ]

    return issues


def _redacted_issue_line(issue: EnvIssue) -> str:
    key = f" {issue.key}" if issue.key else ""
    return f"{issue.severity.upper()} {issue.code}{key}: {issue.message}"


def build_summary(
    env: dict[str, str],
    issues: list[EnvIssue],
    *,
    profile: str,
    template: bool,
    strict_runtime: bool,
) -> dict[str, Any]:
    errors = [i for i in issues if i.severity == STATUS_ERROR]
    warnings = [i for i in issues if i.severity == STATUS_WARNING]
    return {
        "ok": not errors,
        "profile": profile,
        "template": template,
        "strict_runtime": strict_runtime,
        "key_count": len(env),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(i) for i in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--profile", choices=("local", "shadow", "production"), required=True)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--strict-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}", file=sys.stderr)
        return 1

    env = load_dotenv(args.env_file)
    issues = validate_env(
        env,
        profile=args.profile,
        template=args.template,
        strict_runtime=args.strict_runtime,
    )
    summary = build_summary(
        env,
        issues,
        profile=args.profile,
        template=args.template,
        strict_runtime=args.strict_runtime,
    )

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        mode = "template" if args.template else "strict-runtime" if args.strict_runtime else "static"
        print(f"env_10_10_safety: profile={args.profile} mode={mode}")
        print(
            f"ok={str(summary['ok']).lower()} "
            f"errors={summary['error_count']} warnings={summary['warning_count']} "
            f"keys={summary['key_count']}"
        )
        for issue in issues:
            print(_redacted_issue_line(issue))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
