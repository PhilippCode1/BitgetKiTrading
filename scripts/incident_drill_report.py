#!/usr/bin/env python3
"""Incident-Drill-Report fuer Observability/Alerting (synthetisch fail-closed)."""

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
    scenario_ids = [
        "live_broker_down",
        "market_data_stale",
        "risk_timeout",
        "reconcile_drift",
        "safety_latch_active",
        "kill_switch_active",
        "bitget_auth_error",
        "db_unavailable",
        "redis_unavailable",
        "alert_engine_route_test",
        "dashboard_shows_no_go",
        "operator_acknowledges_incident",
    ]
    scenarios = [
        {
            "id": sid,
            "expected": "alert_and_block_live",
            "actual": "alert_and_block_live",
            "pass": True,
        }
        for sid in scenario_ids
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "status": "NOT_ENOUGH_EVIDENCE",
        "verified": False,
        "evidence_level": "synthetic",
        "private_live_allowed": "NO_GO",
        "incident_drill_present": True,
        "delivery_verified": False,
        "slo_baseline_verified": False,
        "scenarios": scenarios,
        "external_required": [
            "real_alert_delivery_proof_missing",
            "real_operator_acknowledgement_proof_missing",
            "real_slo_baseline_missing",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Incident Drill Report",
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
    for s in payload["scenarios"]:
        lines.append(f"- `{s['id']}`: pass=`{s['pass']}`")
    lines.extend(["", "## External Required", ""])
    lines.extend(f"- `{x}`" for x in payload["external_required"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    payload = build_payload()
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "incident_drill_report: "
        f"status={payload['status']} scenarios={len(payload['scenarios'])} private_live={payload['private_live_allowed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
