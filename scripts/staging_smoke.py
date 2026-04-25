#!/usr/bin/env python3
"""Safe staging smoke runner for bitget-btc-ai.

The script validates a staging ENV file, optionally performs read-only HTTP
checks, and writes a redacted Markdown report. It never submits orders and never
prints raw secrets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_env_10_10_safety import load_dotenv  # noqa: E402
from tools.check_staging_profile import validate_staging_profile  # noqa: E402


SECRET_MARKERS = (
    "SECRET",
    "TOKEN",
    "KEY",
    "PASSWORD",
    "PASSPHRASE",
    "AUTHORIZATION",
    "DATABASE_URL",
    "REDIS_URL",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    target: str
    status: str
    detail: str


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def redact_value(key: str, value: str) -> str:
    if not value:
        return ""
    upper_key = key.upper()
    if any(marker in upper_key for marker in SECRET_MARKERS):
        return "***REDACTED***"
    return redact_url(value)


def redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    redacted = parsed._replace(netloc=host, query="", fragment="")
    return urlunsplit(redacted)


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, timeout: float = 20.0) -> tuple[int, object | str]:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return resp.status, {}
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw[:500]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            return exc.code, json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return exc.code, raw[:500]
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def build_check_plan(env: dict[str, str]) -> list[tuple[str, str, str]]:
    gateway = (env.get("API_GATEWAY_URL") or "").rstrip("/")
    auth = env.get("DASHBOARD_GATEWAY_AUTHORIZATION") or ""
    dashboard = env.get("HEALTH_URL_DASHBOARD") or env.get("FRONTEND_URL") or ""
    live_broker = env.get("HEALTH_URL_LIVE_BROKER") or ""
    llm = env.get("HEALTH_URL_LLM_ORCHESTRATOR") or ""
    bitget = env.get("BITGET_READ_ONLY_HEALTH_URL") or f"{gateway}/v1/exchange/readiness"

    return [
        ("gateway_health", f"{gateway}/health", ""),
        ("gateway_ready", f"{gateway}/ready", ""),
        ("system_health", f"{gateway}/v1/system/health", auth),
        ("dashboard_health", dashboard, ""),
        ("live_broker_readiness", live_broker, ""),
        ("llm_orchestrator_readiness", llm, ""),
        ("bitget_read_only", bitget, auth),
    ]


def dry_run_results(env: dict[str, str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, target, _auth in build_check_plan(env):
        if name == "bitget_read_only" and not truthy(env.get("BITGET_READ_ONLY_CHECK_ENABLED")):
            results.append(CheckResult(name, redact_url(target), "skipped", "explicit opt-in is disabled"))
            continue
        results.append(CheckResult(name, redact_url(target), "planned", "dry-run only; no network call"))
    return results


def network_results(env: dict[str, str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, target, auth in build_check_plan(env):
        if name == "bitget_read_only" and not truthy(env.get("BITGET_READ_ONLY_CHECK_ENABLED")):
            results.append(CheckResult(name, redact_url(target), "skipped", "explicit opt-in is disabled"))
            continue
        if not target:
            results.append(CheckResult(name, "", "failed", "target URL is missing"))
            continue
        headers = {"Authorization": auth} if auth else {}
        code, body = http_json(target, headers=headers)
        ok = code == 200
        detail = f"HTTP {code}"
        if isinstance(body, dict) and body:
            detail = f"{detail}; keys={','.join(sorted(str(k) for k in body.keys())[:8])}"
        elif isinstance(body, str) and body:
            detail = f"{detail}; non-json body omitted"
        results.append(CheckResult(name, redact_url(target), "passed" if ok else "failed", detail))
    return results


def report_markdown(
    *,
    env_file: Path,
    env: dict[str, str],
    validation_issues: list[object],
    results: list[CheckResult],
    dry_run: bool,
) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    failed = any(result.status == "failed" for result in results) or bool(validation_issues)
    live_enabled = truthy(env.get("LIVE_TRADE_ENABLE"))
    go_no_go = "NO-GO" if failed or live_enabled else "GO-FOR-STAGING-ONLY"
    lines = [
        "# Staging Smoke Report",
        "",
        f"- Date/Time UTC: `{now}`",
        f"- Git SHA: `{git_sha()}`",
        f"- ENV file: `{env_file.name}`",
        f"- APP_ENV: `{env.get('APP_ENV', '')}`",
        f"- DEPLOY_ENV: `{env.get('DEPLOY_ENV', '')}`",
        f"- Mode: `{'dry-run' if dry_run else 'network-smoke'}`",
        f"- Live trade enabled: `{str(live_enabled).lower()}`",
        f"- Secret safety: raw secrets are redacted; no customer secrets are required by this report.",
        f"- Go/No-Go: `{go_no_go}`",
        "",
        "## Redacted Runtime Values",
        "",
    ]
    for key in (
        "API_GATEWAY_URL",
        "FRONTEND_URL",
        "HEALTH_URL_DASHBOARD",
        "HEALTH_URL_LIVE_BROKER",
        "HEALTH_URL_LLM_ORCHESTRATOR",
        "DATABASE_URL",
        "REDIS_URL",
        "DASHBOARD_GATEWAY_AUTHORIZATION",
    ):
        lines.append(f"- {key}: `{redact_value(key, env.get(key, ''))}`")
    lines.extend(["", "## Validation Issues", ""])
    if validation_issues:
        for issue in validation_issues:
            code = getattr(issue, "code", "unknown")
            key = getattr(issue, "key", None) or "-"
            message = getattr(issue, "message", str(issue))
            lines.append(f"- `{code}` `{key}`: {message}")
    else:
        lines.append("- none")
    lines.extend(["", "## Checks", "", "| Check | Target | Status | Detail |", "| --- | --- | --- | --- |"])
    for result in results:
        lines.append(f"| {result.name} | `{result.target}` | `{result.status}` | {result.detail} |")
    lines.extend(
        [
            "",
            "## Next Steps",
            "",
            "- Keep `LIVE_TRADE_ENABLE=false` for every staging run.",
            "- Attach this report to the release candidate ticket.",
            "- Treat any failed validation or smoke check as a production blocker.",
            "",
            "## Signoff",
            "",
            "- Release ticket:",
            "- Operator:",
            "- Security reviewer:",
            "- Timestamp:",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    env_path = args.env_file if args.env_file.is_absolute() else ROOT / args.env_file
    if not env_path.is_file():
        print(f"ERROR env_file_missing: {env_path}", file=sys.stderr)
        return 1

    env = load_dotenv(env_path)
    template_mode = args.dry_run and env_path.name.endswith(".example")
    validation_issues = validate_staging_profile(env, template=template_mode, strict_runtime=not template_mode)
    results = dry_run_results(env) if args.dry_run else network_results(env)

    print("staging_smoke")
    print(f"env_file={env_path}")
    print(f"mode={'dry-run' if args.dry_run else 'network-smoke'}")
    for key in ("API_GATEWAY_URL", "FRONTEND_URL", "DASHBOARD_GATEWAY_AUTHORIZATION"):
        print(f"{key}={redact_value(key, env.get(key, ''))}")
    for issue in validation_issues:
        print(f"ERROR {issue.code} {issue.key or '-'}: {issue.message}", file=sys.stderr)
    for result in results:
        print(f"{result.name}: {result.status} {result.target} ({result.detail})")

    if args.output_md:
        output_path = args.output_md if args.output_md.is_absolute() else ROOT / args.output_md
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            report_markdown(
                env_file=env_path,
                env=env,
                validation_issues=validation_issues,
                results=results,
                dry_run=args.dry_run,
            ),
            encoding="utf-8",
        )
        print(f"report={output_path}")

    failed = bool(validation_issues) or any(result.status == "failed" for result in results)
    if truthy(env.get("LIVE_TRADE_ENABLE")):
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
