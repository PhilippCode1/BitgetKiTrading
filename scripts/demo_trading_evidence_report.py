#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (ROOT, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from scripts.bitget_demo_readiness import DemoReadiness, build_report
from scripts.bitget_readiness_check import load_dotenv


@dataclass
class DemoTradingEvidence:
    result: str
    live_trading_allowed: bool
    demo_verified: bool
    blockers: list[str]
    warnings: list[str]
    checks: dict[str, str]
    readiness: dict[str, Any]
    private_readonly: dict[str, Any] | None
    order_dry_run: dict[str, Any] | None
    demo_order_smoke: dict[str, Any] | None


def _report_dict(report: DemoReadiness) -> dict[str, Any]:
    return asdict(report)


def _merge_blockers(*reports: DemoReadiness | None) -> list[str]:
    out: list[str] = []
    for rep in reports:
        if rep is None:
            continue
        out.extend(rep.blockers)
    return out


def _merge_warnings(*reports: DemoReadiness | None) -> list[str]:
    out: list[str] = []
    for rep in reports:
        if rep is None:
            continue
        out.extend(rep.warnings)
    return out


def build_evidence(
    env: dict[str, str],
    *,
    run_private_readonly: bool,
    run_order_dry_run: bool,
    run_order_smoke: bool,
    allow_demo_money: bool,
) -> DemoTradingEvidence:
    readiness = build_report(env, "readonly")
    private_readonly: DemoReadiness | None = None
    order_dry_run: DemoReadiness | None = None
    demo_order_smoke: DemoReadiness | None = None

    if run_private_readonly and readiness.result != "FAIL":
        private_readonly = build_report(env, "private-readonly")
    if run_order_dry_run and readiness.result != "FAIL":
        order_dry_run = build_report(env, "demo-order-dry-run")
    if run_order_smoke:
        demo_order_smoke = build_report(
            env,
            "demo-order-smoke",
            allow_demo_money=allow_demo_money,
        )

    blockers = _merge_blockers(readiness, private_readonly, order_dry_run, demo_order_smoke)
    warnings = _merge_warnings(readiness, private_readonly, order_dry_run, demo_order_smoke)
    demo_order_executed = bool(demo_order_smoke and demo_order_smoke.checks.get("demo_order_executed") == "true")
    private_readonly_ok = bool(private_readonly and private_readonly.result != "FAIL")
    readiness_ok = readiness.result != "FAIL"
    dry_run_ok = bool(order_dry_run and order_dry_run.result != "FAIL") or not run_order_dry_run

    if blockers:
        result = "FAILED"
    elif demo_order_executed and private_readonly_ok:
        result = "DEMO_VERIFIED"
    elif private_readonly_ok or (readiness_ok and dry_run_ok):
        result = "DEMO_READY"
    else:
        result = "NOT_ENOUGH_EVIDENCE"

    return DemoTradingEvidence(
        result=result,
        live_trading_allowed=False,
        demo_verified=result == "DEMO_VERIFIED",
        blockers=blockers,
        warnings=warnings,
        checks={
            "readonly_result": readiness.result,
            "private_readonly_result": private_readonly.result if private_readonly else "not_run",
            "order_dry_run_result": order_dry_run.result if order_dry_run else "not_run",
            "demo_order_smoke_result": demo_order_smoke.result if demo_order_smoke else "not_run",
            "demo_order_executed": str(demo_order_executed).lower(),
            "live_trading_allowed": "false",
            "private_live_allowed": "false",
        },
        readiness=_report_dict(readiness),
        private_readonly=_report_dict(private_readonly) if private_readonly else None,
        order_dry_run=_report_dict(order_dry_run) if order_dry_run else None,
        demo_order_smoke=_report_dict(demo_order_smoke) if demo_order_smoke else None,
    )


def to_markdown(rep: DemoTradingEvidence) -> str:
    lines = [
        "# Demo Trading Evidence Report",
        "",
        f"- Ergebnis: `{rep.result}`",
        f"- Demo verifiziert: `{str(rep.demo_verified).lower()}`",
        f"- Echtes Live-Trading erlaubt: `{str(rep.live_trading_allowed).lower()}`",
        "- Hinweis: Demo-Evidence ersetzt keine private_live_allowed-Freigabe.",
        "",
        "## Checks",
        *[f"- `{k}`: `{v}`" for k, v in rep.checks.items()],
        "",
        "## Blocker",
        *([f"- {b}" for b in rep.blockers] if rep.blockers else ["- keine"]),
        "",
        "## Warnungen",
        *([f"- {w}" for w in rep.warnings] if rep.warnings else ["- keine"]),
        "",
        "## Statuslogik",
        "- `DEMO_READY`: Demo-ENV/Readiness ist technisch brauchbar, aber noch keine echte Demo-Order bewiesen.",
        "- `DEMO_VERIFIED`: Private Demo-Read-only und bewusster Demo-Order-Smoke wurden erfolgreich ausgeführt.",
        "- `private_live_allowed` bleibt immer `false`, bis separate Live-/Owner-/Shadow-/Restore-/Alert-Evidence vorhanden ist.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", type=Path, default=Path(".env.demo"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--private-readonly", action="store_true")
    p.add_argument("--order-dry-run", action="store_true")
    p.add_argument("--demo-order-smoke", action="store_true")
    p.add_argument("--i-understand-this-uses-demo-money", action="store_true")
    p.add_argument("--output-md", type=Path, default=Path("reports/demo_trading_evidence.md"))
    p.add_argument("--output-json", type=Path, default=Path("reports/demo_trading_evidence.json"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    env_file = args.env_file
    if args.dry_run and not env_file.exists() and Path(".env.demo.example").exists():
        env_file = Path(".env.demo.example")
    if not env_file.is_file():
        print(f"ERROR env_file_missing: {env_file}")
        return 1

    env = load_dotenv(env_file)
    rep = build_evidence(
        env,
        run_private_readonly=bool(args.private_readonly),
        run_order_dry_run=bool(args.order_dry_run or args.dry_run),
        run_order_smoke=bool(args.demo_order_smoke),
        allow_demo_money=bool(args.i_understand_this_uses_demo_money),
    )

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(to_markdown(rep), encoding="utf-8")
    args.output_json.write_text(json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"demo_trading_evidence: result={rep.result} demo_verified={str(rep.demo_verified).lower()}")
    return 1 if rep.result == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
