#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass
class HealthReport:
    result: str
    checks: dict[str, str]
    warnings: list[str]
    blockers: list[str]


def _get(client: httpx.Client, url: str) -> tuple[int, dict]:
    try:
        response = client.get(url, timeout=8.0)
    except httpx.ReadTimeout:
        return -1, {"_error": "timeout"}
    except Exception as exc:
        return -1, {"_error": type(exc).__name__}
    try:
        payload = response.json() if response.content else {}
    except Exception:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def run(dashboard_url: str, base_url: str) -> HealthReport:
    checks: dict[str, str] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    with httpx.Client() as client:
        dashboard_http, _ = _get(client, dashboard_url)
        checks["dashboard_http"] = str(dashboard_http)
        if dashboard_http == -1:
            blockers.append("dashboard_timeout")
        elif dashboard_http >= 400:
            blockers.append("Dashboard nicht erreichbar.")

        health_http, health_payload = _get(client, f"{base_url.rstrip('/')}/health")
        ready_http, ready_payload = _get(client, f"{base_url.rstrip('/')}/ready")
        checks["gateway_health"] = str(health_http)
        checks["gateway_ready"] = str(ready_http)
        if health_http == -1:
            blockers.append("api_gateway_unreachable")
        if ready_http == -1 or ready_http >= 400:
            blockers.append("ready_failed")
        if (health_http >= 400 and health_http != -1) or (ready_http >= 400 and ready_http != -1):
            blockers.append("API-Gateway Health/Ready nicht erreichbar.")

        demo_status_http, demo_status = _get(client, f"{base_url.rstrip('/')}/api/demo/status")
        demo_readiness_http, demo_readiness = _get(client, f"{base_url.rstrip('/')}/api/demo/readiness")
        checks["demo_status"] = str(demo_status_http)
        checks["demo_readiness"] = str(demo_readiness_http)
        if (
            demo_status_http == -1
            or demo_readiness_http == -1
            or demo_status_http >= 400
            or demo_readiness_http >= 400
        ):
            blockers.append("demo_status_failed")
        if demo_status_http >= 400 and demo_status_http != -1:
            blockers.append("Demo-Status nicht erreichbar.")
        if demo_readiness_http >= 400 and demo_readiness_http != -1:
            blockers.append("Demo-Readiness nicht erreichbar.")

        if bool(((demo_status.get("demo_mode") or {}).get("live_trade_enable"))):
            blockers.append("Live-Trading ist aktiv, muss AUS bleiben.")
        if not bool(((demo_status.get("demo_mode") or {}).get("bitget_demo_enabled"))):
            warnings.append("BITGET_DEMO_ENABLED ist nicht als true sichtbar.")
        if str((demo_readiness.get("result") or "")).upper() == "FAIL":
            blockers.append("Demo-Readiness meldet FAIL.")

        raw = json.dumps(
            {"health": health_payload, "ready": ready_payload, "demo": demo_status},
            ensure_ascii=False,
        ).lower()
        for marker in ("api_secret", "passphrase", "authorization=bearer "):
            if marker in raw:
                blockers.append("Moeglicher Secret-Leak in Endpoint-Ausgabe erkannt.")
                break

    if blockers:
        result = "FAIL"
    elif warnings:
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    return HealthReport(result=result, checks=checks, warnings=warnings, blockers=blockers)


def to_md(rep: HealthReport) -> str:
    return "\n".join(
        [
            "# Demo Stack Healthcheck",
            "",
            f"- Ergebnis: `{rep.result}`",
            "",
            "## Checks",
            *[f"- `{k}`: `{v}`" for k, v in rep.checks.items()],
            "",
            "## Blocker",
            *([f"- {x}" for x in rep.blockers] or ["- keine"]),
            "",
            "## Warnungen",
            *([f"- {x}" for x in rep.warnings] or ["- keine"]),
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=False)
    parser.add_argument("--dashboard-url", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.dashboard_url, args.base_url)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(to_md(report), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"demo_stack_healthcheck: result={report.result}")
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
