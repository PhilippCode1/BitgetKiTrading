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

import httpx

from scripts.bitget_readiness_check import load_dotenv

SECRET_KEYS = (
    "BITGET_API_KEY",
    "BITGET_API_SECRET",
    "BITGET_API_PASSPHRASE",
    "BITGET_DEMO_API_KEY",
    "BITGET_DEMO_API_SECRET",
    "BITGET_DEMO_API_PASSPHRASE",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _present(value: str | None) -> bool:
    raw = (value or "").strip()
    return bool(raw) and "change_me" not in raw.lower()


def _redact_env(env: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in env.items():
        if k in SECRET_KEYS:
            out[k] = "set_redacted" if _present(str(v)) else "missing"
        else:
            out[k] = v
    return out


@dataclass
class DemoReadiness:
    result: str
    blockers: list[str]
    warnings: list[str]
    checks: dict[str, str]
    env_snapshot: dict[str, Any]


def build_report(env: dict[str, str], mode: str) -> DemoReadiness:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, str] = {}

    exec_mode = str(env.get("EXECUTION_MODE") or "").strip().lower()
    live_trade_enable = _truthy(env.get("LIVE_TRADE_ENABLE"))
    demo_enabled = _truthy(env.get("BITGET_DEMO_ENABLED"))
    demo_key_ok = all(
        _present(env.get(k))
        for k in ("BITGET_DEMO_API_KEY", "BITGET_DEMO_API_SECRET", "BITGET_DEMO_API_PASSPHRASE")
    )
    demo_base = str(env.get("BITGET_DEMO_REST_BASE_URL") or "").strip().lower()
    live_base = str(env.get("BITGET_API_BASE_URL") or "").strip().lower()

    checks["execution_mode"] = exec_mode or "missing"
    checks["live_trade_enable"] = str(live_trade_enable).lower()
    checks["bitget_demo_enabled"] = str(demo_enabled).lower()
    checks["demo_keys"] = "ok" if demo_key_ok else "missing"
    checks["demo_endpoint"] = "ok" if demo_base.startswith("https://") else "missing_or_invalid"

    if exec_mode != "bitget_demo":
        blockers.append("EXECUTION_MODE muss bitget_demo sein.")
    if live_trade_enable:
        blockers.append("LIVE_TRADE_ENABLE muss false sein.")
    if not demo_enabled:
        blockers.append("BITGET_DEMO_ENABLED muss true sein.")
    if not demo_key_ok:
        blockers.append("Demo-Credentials fehlen (BITGET_DEMO_*).")
    if not demo_base.startswith("https://"):
        blockers.append("BITGET_DEMO_REST_BASE_URL ist unklar.")
    if live_base and demo_base and live_base == demo_base:
        warnings.append("Demo- und Live-REST-Basis sind identisch; paptrading Header strikt pruefen.")

    if mode == "readonly" and not blockers:
        try:
            with httpx.Client(timeout=8.0) as client:
                r = client.get(f"{demo_base.rstrip('/')}/api/v2/public/time")
                checks["server_time_http"] = str(r.status_code)
                if r.status_code >= 400:
                    blockers.append("Demo-Serverzeit nicht erreichbar.")
        except Exception:
            blockers.append("Demo-Serverzeit nicht erreichbar.")
    else:
        checks["server_time_http"] = "skipped"

    if blockers:
        result = "FAIL"
    elif warnings:
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    return DemoReadiness(
        result=result,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
        env_snapshot=_redact_env(
            {
                "EXECUTION_MODE": env.get("EXECUTION_MODE", ""),
                "LIVE_TRADE_ENABLE": env.get("LIVE_TRADE_ENABLE", ""),
                "BITGET_DEMO_ENABLED": env.get("BITGET_DEMO_ENABLED", ""),
                "BITGET_API_BASE_URL": env.get("BITGET_API_BASE_URL", ""),
                "BITGET_DEMO_REST_BASE_URL": env.get("BITGET_DEMO_REST_BASE_URL", ""),
                **{k: env.get(k, "") for k in SECRET_KEYS},
            }
        ),
    )


def to_markdown(rep: DemoReadiness) -> str:
    lines = [
        "# Bitget Demo Readiness",
        "",
        f"- Ergebnis: `{rep.result}`",
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
        "## Env Snapshot (redacted)",
        "```json",
        json.dumps(rep.env_snapshot, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mode", choices=("readonly",), default="readonly")
    p.add_argument("--output-md", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}")
        return 1
    env = load_dotenv(args.env_file)
    mode = "dry-run" if args.dry_run else args.mode
    report = build_report(env, mode)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(to_markdown(report), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"bitget_demo_readiness: result={report.result} mode={mode}")
        for b in report.blockers:
            print(f"BLOCKER {b}")
        for w in report.warnings:
            print(f"WARNING {w}")
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
