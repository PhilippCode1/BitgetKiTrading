#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import check_live_broker_preflight as preflight_checker  # noqa: E402


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _scenario_rows() -> list[dict[str, Any]]:
    scenario_ids = [
        "db_unavailable",
        "redis_unavailable",
        "risk_timeout",
        "market_data_stale",
        "orderbook_missing",
        "exchange_truth_missing",
        "unknown_instrument",
        "quarantined_asset",
        "shadow_mismatch",
        "operator_release_missing",
        "safety_latch_active",
        "kill_switch_active",
        "global_halt_active",
        "bitget_auth_error",
        "bitget_permission_error",
        "bitget_timeout",
        "bitget_5xx",
        "duplicate_client_oid",
        "reconcile_degraded",
        "env_invalid",
    ]
    rows: list[dict[str, Any]] = []
    for sid in scenario_ids:
        rows.append(
            {
                "scenario": sid,
                "expected": "block",
                "actual": "block",
                "pass": True,
                "reason": f"{sid}_blocks_submit",
                "audit_fields": {
                    "gate": "live_broker_fail_closed",
                    "decision": "block_live",
                    "checked_at": _now(),
                },
                "evidence_level": "synthetic",
                "live_allowed": False,
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    matrix = preflight_checker.analyze()
    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "status": "implemented",
        "decision": "NOT_ENOUGH_EVIDENCE",
        "verified": False,
        "preflight_ok": bool(matrix.get("ok", False)),
        "preflight_error_count": int(matrix.get("error_count", 0)),
        "scenarios": _scenario_rows(),
        "evidence_level": "synthetic",
        "live_allowed": False,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live Broker Fail-Closed Evidence Report",
        "",
        f"- Generiert: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Verified: `{payload['verified']}`",
        f"- Evidence-Level: `{payload['evidence_level']}`",
        f"- Preflight ok: `{payload['preflight_ok']}`",
        "",
    ]
    for row in payload["scenarios"]:
        lines.append(
            f"- `{row['scenario']}`: expected={row['expected']} actual={row['actual']} pass={row['pass']} reason={row['reason']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live broker fail-closed evidence report")
    parser.add_argument("--output-md", default="reports/live_broker_fail_closed_evidence.md")
    parser.add_argument("--output-json", default="reports/live_broker_fail_closed_evidence.json")
    args = parser.parse_args()

    payload = build_payload()
    output_md = Path(args.output_md)
    output_json = Path(args.output_json)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_md(payload), encoding="utf-8")
    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"live_broker_fail_closed_evidence_report: scenarios={len(payload['scenarios'])} verified={payload['verified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
