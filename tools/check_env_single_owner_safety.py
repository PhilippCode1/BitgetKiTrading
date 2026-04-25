#!/usr/bin/env python3
"""Validate private single-owner ENV safety for bitget-btc-ai."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCOPE_DOC = ROOT / "docs" / "production_10_10" / "private_owner_scope.md"
GERMAN_UI_DOC = ROOT / "docs" / "production_10_10" / "german_only_ui_policy.md"
SAFETY_DOC = ROOT / "docs" / "production_10_10" / "env_secrets_single_owner_safety.md"

STATUS_ERROR = "error"
STATUS_WARNING = "warning"
BOOL_TRUE = {"1", "true", "yes", "on"}
BOOL_FALSE = {"0", "false", "no", "off", ""}

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
    "ADMIN_TOKEN",
    "DASHBOARD_GATEWAY",
    "TELEGRAM_BOT",
    "STRIPE",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[0-9a-zA-Z]{20,}"),
    re.compile(r"sk-(?:proj|test|live)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)

BASE_REQUIRED_KEYS = {
    "PRODUCTION",
    "APP_ENV",
    "DEBUG",
    "EXECUTION_MODE",
    "LIVE_TRADE_ENABLE",
    "LIVE_BROKER_ENABLED",
    "LLM_USE_FAKE_PROVIDER",
    "NEWS_FIXTURE_MODE",
    "BITGET_DEMO_ENABLED",
    "BITGET_RELAX_CREDENTIAL_ISOLATION",
}

RUNTIME_SECRET_KEYS = {
    "ADMIN_TOKEN",
    "DATABASE_URL",
    "ENCRYPTION_KEY",
    "GATEWAY_JWT_SECRET",
    "INTERNAL_API_KEY",
    "JWT_SECRET",
    "POSTGRES_PASSWORD",
    "REDIS_URL",
    "SECRET_KEY",
}


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
        value = _strip_inline_comment(value.strip())
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        env[key.strip()] = value
    return env


def dotenv_parse_issues(path: Path) -> list[str]:
    issues: list[str] = []
    for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            issues.append(f"line {index}: missing '=' assignment")
    return issues


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    out: list[str] = []
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                break
        out.append(char)
    return "".join(out).strip()


def truthy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in BOOL_TRUE


def falsy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in BOOL_FALSE


def is_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    if lower.startswith("bearer "):
        lower = lower[7:].strip()
    if lower.startswith("<") and lower.endswith(">"):
        return True
    return any(marker in lower for marker in PLACEHOLDER_MARKERS)


def _has_loopback(value: str) -> bool:
    if not value.strip():
        return False
    parts = [item.strip() for item in value.split(",") if item.strip()] or [value]
    for part in parts:
        parsed = urlparse(part)
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        lowered = part.lower()
        if lowered.startswith(("http://localhost", "https://localhost")):
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
    prod_like = profile == "production" or truthy(env, "PRODUCTION") or env.get("APP_ENV") == "production"
    shadow_like = profile == "shadow" or env.get("APP_ENV") == "shadow" or env.get("EXECUTION_MODE") == "shadow"

    expected_app_env = {"production": "production", "shadow": "shadow", "local": "local"}.get(profile)
    if expected_app_env and env.get("APP_ENV") and env.get("APP_ENV") != expected_app_env:
        _issue(issues, "profile_app_env_mismatch", f"profile={profile} expects APP_ENV={expected_app_env}.", "APP_ENV")

    for key in BASE_REQUIRED_KEYS:
        if key not in env:
            _issue(issues, "missing_required_key", "required single-owner safety key is absent.", key)

    for key, value in sorted(env.items()):
        key_u = key.upper()
        if key_u.startswith("NEXT_PUBLIC_"):
            if any(fragment in key_u for fragment in BROWSER_FORBIDDEN_FRAGMENTS):
                _issue(issues, "browser_secret_key_name", "NEXT_PUBLIC_* must not expose secret-like names.", key)
            if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
                _issue(issues, "browser_secret_value", "NEXT_PUBLIC_* value looks like a raw secret.", key)
        if strict_runtime and key_u in RUNTIME_SECRET_KEYS and is_placeholder(value):
            _issue(issues, "placeholder_runtime_secret", "runtime secret is blank or placeholder.", key)

    if prod_like:
        if "BITGET_RELAX_CREDENTIAL_ISOLATION" in env and not falsy(env, "BITGET_RELAX_CREDENTIAL_ISOLATION"):
            _issue(
                issues,
                "production_relaxed_credential_isolation_forbidden",
                "BITGET_RELAX_CREDENTIAL_ISOLATION must be false in production.",
                "BITGET_RELAX_CREDENTIAL_ISOLATION",
            )
        for key in (
            "DEBUG",
            "LLM_USE_FAKE_PROVIDER",
            "NEWS_FIXTURE_MODE",
            "BITGET_DEMO_ENABLED",
        ):
            if truthy(env, key):
                _issue(issues, "production_forbidden_true", "value must not be true in production.", key)
        for key, value in env.items():
            if key.endswith("_URL") or key in {
                "API_GATEWAY_URL",
                "APP_BASE_URL",
                "CORS_ALLOW_ORIGINS",
                "DATABASE_URL",
                "DATABASE_URL_DOCKER",
                "FRONTEND_URL",
                "NEXT_PUBLIC_API_BASE_URL",
                "NEXT_PUBLIC_WS_BASE_URL",
                "REDIS_URL",
                "REDIS_URL_DOCKER",
            }:
                if strict_runtime and _has_loopback(value):
                    _issue(issues, "production_loopback_url", "loopback URL is forbidden in production runtime.", key)
        if truthy(env, "PAYMENT_MOCK_ENABLED"):
            _issue(
                issues,
                "production_payment_mock_present",
                "Payment mock is out-of-scope and dangerous in production; not required for private owner scope.",
                "PAYMENT_MOCK_ENABLED",
                severity=STATUS_WARNING,
            )

    if shadow_like and truthy(env, "LIVE_TRADE_ENABLE"):
        _issue(issues, "shadow_live_trade_enabled", "shadow mode must not enable live order submission.", "LIVE_TRADE_ENABLE")
    if shadow_like and truthy(env, "LLM_USE_FAKE_PROVIDER"):
        _issue(issues, "shadow_fake_provider_enabled", "shadow must use real data/provider paths, not fake provider.", "LLM_USE_FAKE_PROVIDER")

    if profile == "local":
        if truthy(env, "LLM_USE_FAKE_PROVIDER") or truthy(env, "BITGET_DEMO_ENABLED"):
            _issue(
                issues,
                "local_not_production_ready",
                "local may use fake/demo providers but is not production-ready.",
                severity=STATUS_WARNING,
            )

    if truthy(env, "LIVE_TRADE_ENABLE"):
        required_true = (
            ("EXECUTION_MODE", "live", "live_trade_requires_live_execution_mode"),
            ("LIVE_BROKER_ENABLED", "true", "live_trade_requires_live_broker"),
            ("LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN", "true", "live_trade_requires_operator_release"),
            ("REQUIRE_SHADOW_MATCH_BEFORE_LIVE", "true", "live_trade_requires_shadow_match"),
            ("LIVE_REQUIRE_EXCHANGE_HEALTH", "true", "live_trade_requires_exchange_health"),
            ("RISK_HARD_GATING_ENABLED", "true", "live_trade_requires_risk_governor"),
            ("LIVE_KILL_SWITCH_ENABLED", "true", "live_trade_requires_kill_switch"),
        )
        for key, expected, code in required_true:
            actual_ok = env.get(key) == expected if key == "EXECUTION_MODE" else truthy(env, key)
            if not actual_ok:
                _issue(issues, code, f"LIVE_TRADE_ENABLE=true requires {key}={expected}.", key)
        asset_gate_keys = (
            "LIVE_REQUIRE_ASSET_ELIGIBILITY",
            "ASSET_LIVE_ELIGIBILITY_REQUIRED",
            "BITGET_ASSET_LIVE_ELIGIBILITY_REQUIRED",
        )
        if not any(truthy(env, key) for key in asset_gate_keys if key in env):
            _issue(
                issues,
                "live_trade_requires_asset_eligibility",
                "LIVE_TRADE_ENABLE=true requires explicit asset live-eligibility gate.",
                "LIVE_REQUIRE_ASSET_ELIGIBILITY",
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
                "LIVE_TRADE_ENABLE=true requires safety-latch/manual-action support.",
                "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL",
            )

    demo_enabled = truthy(env, "BITGET_DEMO_ENABLED")
    live_keys = any(
        _actual_secret_value_present(env, key)
        for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE")
    )
    demo_keys = any(
        _actual_secret_value_present(env, key)
        for key in ("BITGET_DEMO_API_KEY", "BITGET_DEMO_API_SECRET", "BITGET_DEMO_API_PASSPHRASE")
    )
    if demo_enabled and live_keys:
        _issue(issues, "bitget_demo_live_key_mix", "Demo mode must not be combined with live Bitget credentials.", "BITGET_DEMO_ENABLED")
    if live_keys and demo_keys:
        _issue(issues, "bitget_demo_live_key_mix", "Demo and live Bitget credential sets must not be present together.", "BITGET_API_KEY")

    if not PRIVATE_SCOPE_DOC.is_file():
        _issue(issues, "private_scope_doc_missing", "private owner scope doc must exist.", None)
    if not GERMAN_UI_DOC.is_file():
        _issue(issues, "german_ui_policy_missing", "German Main Console policy must exist.", None)
    if not SAFETY_DOC.is_file():
        _issue(issues, "single_owner_env_doc_missing", "single-owner ENV safety doc must exist.", None)

    if template:
        issues = [
            issue
            for issue in issues
            if issue.code not in {"placeholder_runtime_secret"}
        ]
    if strict_runtime and template:
        _issue(issues, "mode_conflict", "--template and --strict-runtime are mutually exclusive.")
    return issues


def build_summary(
    env: dict[str, str],
    issues: list[EnvIssue],
    *,
    profile: str,
    template: bool,
    strict_runtime: bool,
) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == STATUS_ERROR]
    warnings = [issue for issue in issues if issue.severity == STATUS_WARNING]
    return {
        "ok": not errors,
        "profile": profile,
        "template": template,
        "strict_runtime": strict_runtime,
        "key_count": len(env),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(issue) for issue in issues],
    }


def _redacted_issue_line(issue: EnvIssue) -> str:
    key = f" {issue.key}" if issue.key else ""
    return f"{issue.severity.upper()} {issue.code}{key}: {issue.message}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--profile", choices=("local", "shadow", "production"), required=True)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--strict-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}")
        return 1
    parse_issues = dotenv_parse_issues(args.env_file)
    if parse_issues:
        print(f"ERROR env_parse_error: {args.env_file}")
        for issue in parse_issues:
            print(f"ERROR env_parse_error_detail: {issue}")
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
        print(f"env_single_owner_safety: profile={args.profile} mode={mode}")
        print(
            f"ok={str(summary['ok']).lower()} errors={summary['error_count']} "
            f"warnings={summary['warning_count']} keys={summary['key_count']}"
        )
        for issue in issues:
            print(_redacted_issue_line(issue))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
