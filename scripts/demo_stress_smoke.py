#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

import httpx

SAFE_PATHS = (
    "/health",
    "/ready",
    "/api/demo/status",
    "/api/demo/readiness",
    "/api/demo/assets",
    "/api/demo/balance",
    "/api/demo/open-orders",
    "/api/demo/order-history",
)


@dataclass
class SmokeReport:
    result: str
    duration_sec: int
    checks_total: int
    checks_failed: int
    submit_tested: bool
    preview_tested: bool
    submit_allowed: bool
    demo_money_used: bool
    blockers: list[str]


def run(
    base_url: str,
    dashboard_url: str,
    duration_sec: int,
    include_preview: bool,
    include_submit: bool,
    allow_demo_money: bool = False,
) -> SmokeReport:
    start = time.time()
    total = 0
    failed = 0
    blockers: list[str] = []
    submit_allowed = False
    demo_money_used = False
    with httpx.Client(timeout=6.0) as client:
        while time.time() - start < max(1, duration_sec):
            for path in SAFE_PATHS:
                total += 1
                try:
                    r = client.get(f"{base_url.rstrip('/')}{path}")
                    if r.status_code >= 500:
                        failed += 1
                except Exception:
                    failed += 1
            try:
                d = client.get(dashboard_url)
                total += 1
                if d.status_code >= 500:
                    failed += 1
            except Exception:
                total += 1
                failed += 1
            time.sleep(1)

        if include_preview:
            total += 1
            r = client.post(f"{base_url.rstrip('/')}/api/demo/order/preview")
            if r.status_code >= 500:
                failed += 1
                blockers.append("Demo-Preview antwortet mit 5xx.")
        if include_submit:
            total += 1
            if not allow_demo_money:
                blockers.append(
                    "Demo-Submit wurde angefordert, aber Sicherheitsflag --i-understand-this-uses-demo-money fehlt."
                )
            else:
                r = client.post(f"{base_url.rstrip('/')}/api/demo/order/submit")
                if r.status_code >= 500:
                    failed += 1
                    blockers.append("Demo-Submit antwortet mit 5xx.")
                else:
                    body = r.json() if r.content else {}
                    submit_allowed = bool(body.get("allowed"))
                    demo_money_used = submit_allowed

    if failed > 0 or blockers:
        result = "FAIL"
    else:
        result = "PASS"
    return SmokeReport(
        result=result,
        duration_sec=duration_sec,
        checks_total=total,
        checks_failed=failed,
        submit_tested=include_submit,
        preview_tested=include_preview,
        submit_allowed=submit_allowed,
        demo_money_used=demo_money_used,
        blockers=blockers,
    )


def to_md(rep: SmokeReport) -> str:
    return "\n".join(
        [
            "# Demo Stress Smoke",
            "",
            f"- Ergebnis: `{rep.result}`",
            f"- Dauer (s): `{rep.duration_sec}`",
            f"- Checks: `{rep.checks_total}`",
            f"- Fehlgeschlagen: `{rep.checks_failed}`",
            f"- Preview getestet: `{str(rep.preview_tested).lower()}`",
            f"- Submit getestet: `{str(rep.submit_tested).lower()}`",
            f"- Submit erlaubt: `{str(rep.submit_allowed).lower()}`",
            f"- Demo-Geld genutzt: `{str(rep.demo_money_used).lower()}`",
            "- Echtes Live-Trading: `false`",
            "",
            "## Blocker",
            *([f"- {x}" for x in rep.blockers] or ["- keine"]),
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--dashboard-url", required=True)
    p.add_argument("--duration-sec", type=int, default=60)
    p.add_argument("--output-md")
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-demo-order-preview", action="store_true")
    p.add_argument("--include-demo-order-submit", action="store_true")
    p.add_argument("--i-understand-this-uses-demo-money", action="store_true")
    args = p.parse_args(argv)
    rep = run(
        base_url=args.base_url,
        dashboard_url=args.dashboard_url,
        duration_sec=args.duration_sec,
        include_preview=args.include_demo_order_preview,
        include_submit=args.include_demo_order_submit,
        allow_demo_money=bool(args.i_understand_this_uses_demo_money),
    )
    if args.output_md:
        from pathlib import Path

        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_md(rep), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(rep), ensure_ascii=False, indent=2))
    else:
        print(f"demo_stress_smoke: result={rep.result}")
    return 1 if rep.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
