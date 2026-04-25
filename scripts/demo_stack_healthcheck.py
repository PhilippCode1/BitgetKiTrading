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
    r = client.get(url, timeout=8.0)
    try:
        payload = r.json() if r.content else {}
    except Exception:
        payload = {}
    return r.status_code, payload if isinstance(payload, dict) else {}


def run(dashboard_url: str, base_url: str) -> HealthReport:
    checks: dict[str, str] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    with httpx.Client() as client:
        ds, _ = _get(client, dashboard_url)
        checks["dashboard"] = str(ds)
        if ds >= 400:
            blockers.append("Dashboard nicht erreichbar.")

        hs, hp = _get(client, f"{base_url.rstrip('/')}/health")
        rs, rp = _get(client, f"{base_url.rstrip('/')}/ready")
        checks["gateway_health"] = str(hs)
        checks["gateway_ready"] = str(rs)
        if hs >= 400 or rs >= 400:
            blockers.append("API-Gateway Health/Ready nicht erreichbar.")

        ds_status, demo_status = _get(client, f"{base_url.rstrip('/')}/api/demo/status")
        dr_status, demo_readiness = _get(client, f"{base_url.rstrip('/')}/api/demo/readiness")
        checks["demo_status"] = str(ds_status)
        checks["demo_readiness"] = str(dr_status)
        if ds_status >= 400:
            blockers.append("Demo-Status nicht erreichbar.")
        if dr_status >= 400:
            blockers.append("Demo-Readiness nicht erreichbar.")

        if bool(((demo_status.get("demo_mode") or {}).get("live_trade_enable"))):
            blockers.append("Live-Trading ist aktiv, muss AUS bleiben.")
        if not bool(((demo_status.get("demo_mode") or {}).get("bitget_demo_enabled"))):
            warnings.append("BITGET_DEMO_ENABLED ist nicht als true sichtbar.")
        if str((demo_readiness.get("result") or "")).upper() == "FAIL":
            blockers.append("Demo-Readiness meldet FAIL.")

        # einfache Secret-Leak-Heuristik
        raw = json.dumps({"health": hp, "ready": rp, "demo": demo_status}, ensure_ascii=False).lower()
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
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", type=Path, required=False)
    p.add_argument("--dashboard-url", required=True)
    p.add_argument("--base-url", required=True)
    p.add_argument("--output-md", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    rep = run(args.dashboard_url, args.base_url)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(to_md(rep), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(rep), ensure_ascii=False, indent=2))
    else:
        print(f"demo_stack_healthcheck: result={rep.result}")
    return 1 if rep.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
