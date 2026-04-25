#!/usr/bin/env python3
"""Static checker for the bitget-btc-ai staging profile."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_env_10_10_safety import (  # noqa: E402
    STATUS_ERROR,
    EnvIssue,
    is_placeholder,
    load_dotenv,
    validate_env,
)


@dataclass(frozen=True)
class StagingIssue:
    severity: str
    code: str
    key: str | None
    message: str


def _truthy(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in {"1", "true", "yes", "on"}


def _host(value: str) -> str:
    return (urlparse(value).hostname or value).lower()


def _is_loopback(value: str) -> bool:
    host = _host(value)
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _looks_production_host(value: str) -> bool:
    host = _host(value)
    return bool(host) and "staging" not in host and (
        ".prod." in host
        or ".production." in host
        or host.startswith("prod-")
        or host.startswith("production-")
        or host.endswith(".prod")
    )


def _issue(
    issues: list[StagingIssue],
    code: str,
    message: str,
    key: str | None = None,
) -> None:
    issues.append(StagingIssue("error", code, key, message))


def validate_staging_profile(
    env: dict[str, str],
    *,
    template: bool = False,
    strict_runtime: bool = False,
) -> list[StagingIssue]:
    issues: list[StagingIssue] = []

    if env.get("APP_ENV") != "shadow":
        _issue(issues, "staging_app_env", "Staging uses APP_ENV=shadow.", "APP_ENV")
    if env.get("DEPLOY_ENV") != "staging":
        _issue(issues, "staging_deploy_env", "Staging requires DEPLOY_ENV=staging.", "DEPLOY_ENV")
    if env.get("APP_ENV") == "production" or env.get("DEPLOY_ENV") == "production":
        _issue(issues, "staging_not_production", "Staging must not identify as production.")
    if _truthy(env, "DEBUG"):
        _issue(issues, "debug_forbidden", "DEBUG must be false.", "DEBUG")
    if _truthy(env, "LIVE_TRADE_ENABLE"):
        _issue(issues, "live_trade_forbidden", "Staging must never enable live order submit.", "LIVE_TRADE_ENABLE")
    if not _truthy(env, "LIVE_BROKER_ENABLED"):
        _issue(issues, "live_broker_expected", "Staging should run live-broker read paths with submits disabled.", "LIVE_BROKER_ENABLED")
    if not _truthy(env, "GATEWAY_ENFORCE_SENSITIVE_AUTH"):
        _issue(issues, "auth_required", "Gateway sensitive auth must be enforced.", "GATEWAY_ENFORCE_SENSITIVE_AUTH")
    if env.get("API_AUTH_MODE") in {"", "none"}:
        _issue(issues, "api_auth_required", "API_AUTH_MODE must not be none.", "API_AUTH_MODE")
    if _truthy(env, "LLM_USE_FAKE_PROVIDER"):
        _issue(issues, "fake_llm_forbidden", "Real staging burn-in must not use fake LLM provider.", "LLM_USE_FAKE_PROVIDER")
    if _truthy(env, "NEWS_FIXTURE_MODE"):
        _issue(issues, "fixture_news_forbidden", "Real staging burn-in must not use news fixtures.", "NEWS_FIXTURE_MODE")
    if _truthy(env, "BITGET_DEMO_ENABLED"):
        _issue(issues, "bitget_demo_forbidden", "Staging uses read-only/live-like checks, not demo mode.", "BITGET_DEMO_ENABLED")
    if _truthy(env, "BITGET_WRITE_ENABLED"):
        _issue(issues, "bitget_write_forbidden", "Bitget write capability is forbidden in staging.", "BITGET_WRITE_ENABLED")
    if not _truthy(env, "REQUIRE_SHADOW_MATCH_BEFORE_LIVE"):
        _issue(issues, "shadow_match_required", "Staging prepares shadow-match gate.", "REQUIRE_SHADOW_MATCH_BEFORE_LIVE")
    if not _truthy(env, "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN"):
        _issue(issues, "operator_release_required", "Staging prepares operator-release gate.", "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN")
    if not _truthy(env, "RISK_HARD_GATING_ENABLED"):
        _issue(issues, "risk_gate_required", "Risk hard gating must be enabled.", "RISK_HARD_GATING_ENABLED")

    for key in (
        "API_GATEWAY_URL",
        "FRONTEND_URL",
        "NEXT_PUBLIC_API_BASE_URL",
        "HEALTH_URL_API_GATEWAY",
        "HEALTH_URL_DASHBOARD",
        "HEALTH_URL_LIVE_BROKER",
        "HEALTH_URL_LLM_ORCHESTRATOR",
    ):
        if not env.get(key):
            _issue(issues, "missing_url", "Required staging URL is missing.", key)
        elif strict_runtime and _is_loopback(env[key]):
            _issue(issues, "loopback_forbidden", "Loopback URL is forbidden in staging runtime.", key)

    for key in ("DATABASE_URL", "DATABASE_URL_DOCKER", "REDIS_URL", "REDIS_URL_DOCKER"):
        value = env.get(key, "")
        if not value:
            _issue(issues, "missing_datastore", "Staging datastore URL is missing.", key)
        if _looks_production_host(value):
            _issue(issues, "production_datastore_forbidden", "Staging datastore must not point to production.", key)
        if strict_runtime and _is_loopback(value):
            _issue(issues, "loopback_datastore_forbidden", "Loopback datastore is forbidden in staging runtime.", key)

    for key in (
        "INTERNAL_API_KEY",
        "GATEWAY_JWT_SECRET",
        "DASHBOARD_GATEWAY_AUTHORIZATION",
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "OPENAI_API_KEY",
        "TELEGRAM_BOT_TOKEN",
    ):
        if key not in env:
            _issue(issues, "missing_secret_key", "Required staging secret key name is absent.", key)
        elif strict_runtime and is_placeholder(env[key]):
            _issue(issues, "placeholder_runtime_secret", "Runtime staging secret is blank or placeholder.", key)

    base_issues: list[EnvIssue] = validate_env(
        env,
        profile="shadow",
        template=template,
        strict_runtime=strict_runtime,
    )
    for item in base_issues:
        if item.severity == STATUS_ERROR:
            issues.append(
                StagingIssue(
                    item.severity,
                    f"env10:{item.code}",
                    item.key,
                    item.message,
                )
            )
    return issues


def build_summary(env: dict[str, str], issues: list[StagingIssue], *, mode: str) -> dict[str, object]:
    return {
        "ok": not issues,
        "mode": mode,
        "key_count": len(env),
        "error_count": len(issues),
        "issues": [asdict(issue) for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true")
    mode.add_argument("--strict-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = args.env_file if args.env_file.is_absolute() else ROOT / args.env_file
    if not path.is_file():
        print(f"ERROR env_file_missing: {path}", file=sys.stderr)
        return 1

    env = load_dotenv(path)
    mode_name = "template" if args.template else "strict-runtime"
    issues = validate_staging_profile(
        env,
        template=args.template,
        strict_runtime=args.strict_runtime,
    )
    summary = build_summary(env, issues, mode=mode_name)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"staging_profile_check: mode={mode_name}")
        print(f"ok={str(summary['ok']).lower()} errors={summary['error_count']} keys={summary['key_count']}")
        for issue in issues:
            key = f" {issue.key}" if issue.key else ""
            print(f"ERROR {issue.code}{key}: {issue.message}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
