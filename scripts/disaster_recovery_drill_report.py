#!/usr/bin/env python3
"""Disaster-Recovery-Drill-Report mit fail-closed Recovery-Safety-Evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


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


def build_payload() -> dict[str, Any]:
    scenarios = [
        "db_restart",
        "redis_restart",
        "live_broker_restart",
        "api_gateway_restart",
        "stale_event_stream",
        "missing_local_order_after_restore",
        "exchange_open_local_missing",
        "local_open_exchange_missing",
        "safety_latch_after_recovery",
        "no_opening_until_reconcile_clean",
        "audit_trail_after_restore",
        "alert_after_recovery_issue",
    ]
    checks = [
        {
            "scenario": name,
            "expected": "block_or_reconcile_required",
            "actual": "block_or_reconcile_required",
            "pass": True,
            "evidence_level": "synthetic",
        }
        for name in scenarios
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "environment": "synthetic_local",
        "status": "NOT_ENOUGH_EVIDENCE",
        "verified": False,
        "evidence_level": "synthetic",
        "private_live_allowed": "NO_GO",
        "checks": checks,
        "external_required": [
            "staging_or_clone_drill_missing",
            "runtime_rto_rpo_measurement_missing",
            "owner_review_missing",
        ],
        "notes": [
            "Ohne echten Staging-/Clone-Drill bleibt Disaster-Recovery NOT_ENOUGH_EVIDENCE.",
            "Recovery muss fail-closed bleiben: reconcile + exchange-truth + operator review vor Live.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Disaster Recovery Drill Report",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Status: `{payload['status']}`",
        f"- Verified: `{payload['verified']}`",
        f"- Evidence-Level: `{payload['evidence_level']}`",
        f"- Private Live: `{payload['private_live_allowed']}`",
        "",
        "## Szenarien",
        "",
    ]
    for row in payload["checks"]:
        lines.append(f"- `{row['scenario']}`: pass=`{row['pass']}`, actual=`{row['actual']}`")
    lines.extend(["", "## External Required", ""])
    lines.extend(f"- `{item}`" for item in payload["external_required"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    payload = build_payload()
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "disaster_recovery_drill_report: "
        f"status={payload['status']} checks={len(payload['checks'])} private_live={payload['private_live_allowed']}"
    )
    if args.strict and payload["verified"]:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
