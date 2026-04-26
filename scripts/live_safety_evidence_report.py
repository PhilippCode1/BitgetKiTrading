#!/usr/bin/env python3
"""Kombinierter Kill-Switch-/Safety-Latch-/Emergency-Flatten-Evidence-Report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scripts.live_safety_drill import (  # noqa: E402
    DEFAULT_DRILL_TEMPLATE,
    assess_external_safety_drill,
    secret_surface_issues,
    simulate_safety_drill,
)
from shared_py.main_console_safety import (  # noqa: E402
    SafetyCenterSnapshot,
    emergency_flatten_is_reduce_only,
    live_blocked_by_safety_center,
)

REQUIRED_SAFETY_BLOCKERS = (
    "kill_switch_arm_not_verified",
    "kill_switch_opening_submit_not_blocked",
    "kill_switch_release_not_operator_gated",
    "safety_latch_arm_not_verified",
    "safety_latch_submit_not_blocked",
    "safety_latch_replace_not_blocked",
    "safety_latch_release_reason_not_required",
    "emergency_flatten_not_tested",
    "emergency_flatten_not_reduce_only",
    "emergency_flatten_exchange_truth_not_checked",
    "emergency_flatten_no_increase_not_confirmed",
    "cancel_all_not_tested",
    "audit_trail_not_verified",
    "alert_delivery_not_verified",
    "main_console_state_not_verified",
    "reconcile_after_drill_not_ok",
)


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


def _load_template() -> dict[str, Any]:
    loaded = json.loads(DEFAULT_DRILL_TEMPLATE.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{DEFAULT_DRILL_TEMPLATE} muss ein JSON-Objekt enthalten.")
    return loaded


def _main_console_safety_cases() -> list[dict[str, Any]]:
    cases = [
        (
            "kill_switch_active",
            SafetyCenterSnapshot(
                reconcile_status="ok",
                kill_switch_active=True,
                safety_latch_active=False,
                exchange_truth_status="ok",
                backend_connected=True,
            ),
        ),
        (
            "safety_latch_active",
            SafetyCenterSnapshot(
                reconcile_status="ok",
                kill_switch_active=False,
                safety_latch_active=True,
                exchange_truth_status="ok",
                backend_connected=True,
            ),
        ),
        (
            "reconcile_fail",
            SafetyCenterSnapshot(
                reconcile_status="fail",
                kill_switch_active=False,
                safety_latch_active=False,
                exchange_truth_status="ok",
                backend_connected=True,
            ),
        ),
        (
            "exchange_truth_missing",
            SafetyCenterSnapshot(
                reconcile_status="ok",
                kill_switch_active=False,
                safety_latch_active=False,
                exchange_truth_status="not_checked",
                backend_connected=True,
            ),
        ),
    ]
    return [
        {
            "id": case_id,
            "blocked": live_blocked_by_safety_center(snapshot),
            "snapshot": asdict(snapshot),
        }
        for case_id, snapshot in cases
    ]


def _emergency_flatten_cases() -> list[dict[str, Any]]:
    raw_cases = [
        ("valid_reduce_only", True, 0.4, 1.0, True),
        ("not_reduce_only", False, 0.4, 1.0, False),
        ("would_increase_exposure", True, 1.5, 1.0, False),
        ("missing_position_truth", True, 0.4, 0.0, False),
    ]
    return [
        {
            "id": case_id,
            "reduce_only": reduce_only,
            "requested_qty": requested_qty,
            "position_qty": position_qty,
            "safe": emergency_flatten_is_reduce_only(
                reduce_only=reduce_only,
                requested_qty=requested_qty,
                position_qty=position_qty,
            ),
            "expected_safe": expected_safe,
        }
        for case_id, reduce_only, requested_qty, position_qty, expected_safe in raw_cases
    ]


def build_report_payload() -> dict[str, Any]:
    template = _load_template()
    assessment = assess_external_safety_drill(template)
    secret_issues = secret_surface_issues(template)
    simulated = simulate_safety_drill("simulated")
    main_console_cases = _main_console_safety_cases()
    flatten_cases = _emergency_flatten_cases()

    missing_required_blockers = sorted(set(REQUIRED_SAFETY_BLOCKERS) - set(assessment.blockers))
    main_console_failures = [case["id"] for case in main_console_cases if case["blocked"] is not True]
    flatten_failures = [
        case["id"] for case in flatten_cases if case["safe"] is not case["expected_safe"]
    ]

    failures: list[str] = []
    if assessment.status != "FAIL":
        failures.append("external_template_must_fail_until_real_safety_evidence")
    if secret_issues:
        failures.append("unredacted_secret_surface_detected")
    if missing_required_blockers:
        failures.append("external_template_missing_required_blocker_coverage")
    if simulated.go_no_go != "NO_GO" or simulated.live_write_allowed:
        failures.append("simulated_safety_drill_does_not_block_live")
    if not simulated.opening_order_blocked_by_kill_switch:
        failures.append("kill_switch_simulation_does_not_block_opening")
    if not simulated.opening_order_blocked_by_safety_latch:
        failures.append("safety_latch_simulation_does_not_block_opening")
    if not simulated.emergency_flatten_safe:
        failures.append("emergency_flatten_simulation_not_safe")
    if main_console_failures:
        failures.append("main_console_safety_cases_not_blocking")
    if flatten_failures:
        failures.append("emergency_flatten_reduce_only_cases_failed")

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "external_template": {
            "path": str(DEFAULT_DRILL_TEMPLATE.relative_to(ROOT)),
            "status": assessment.status,
            "blockers": assessment.blockers,
            "warnings": assessment.warnings,
            "secret_surface_issues": secret_issues,
            "missing_required_blockers": missing_required_blockers,
        },
        "simulation": asdict(simulated),
        "main_console_cases": main_console_cases,
        "emergency_flatten_cases": flatten_cases,
        "external_required": [
            "real_staging_shadow_kill_switch_drill_missing",
            "real_staging_shadow_safety_latch_drill_missing",
            "real_emergency_flatten_reduce_only_drill_missing",
            "audit_alert_reconcile_main_console_safety_evidence_missing",
            "owner_signed_live_safety_acceptance_missing",
        ],
        "failures": failures,
        "notes": [
            "Dieser Report beweist repo-lokale Safety-Contracts und Simulationen, nicht echte Live-Freigabe.",
            "Das Repo-Template muss ohne externe Evidence FAIL bleiben.",
            "Emergency-Flatten ist nur akzeptabel, wenn reduce-only, exchange-truth-geprueft und nicht exposure-erhoehend belegt ist.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Live Safety Evidence Report",
        "",
        "Status: kombinierter repo-lokaler Nachweis fuer Kill-Switch, Safety-Latch und Emergency-Flatten ohne echte Exchange-Orders.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- External Required: `{len(payload['external_required'])}`",
        f"- External Template Status: `{payload['external_template']['status']}`",
        f"- External Template Blocker: `{len(payload['external_template']['blockers'])}`",
        "",
        "## Safety-Simulation",
        "",
        f"- Kill-Switch blockiert Opening: `{payload['simulation']['opening_order_blocked_by_kill_switch']}`",
        f"- Safety-Latch blockiert Opening: `{payload['simulation']['opening_order_blocked_by_safety_latch']}`",
        f"- Emergency-Flatten safe/reduce-only: `{payload['simulation']['emergency_flatten_safe']}`",
        f"- Live-Write erlaubt: `{payload['simulation']['live_write_allowed']}`",
        "",
        "## Emergency-Flatten-Cases",
        "",
    ]
    for case in payload["emergency_flatten_cases"]:
        lines.append(
            f"- `{case['id']}`: safe=`{case['safe']}`, expected=`{case['expected_safe']}`"
        )
    lines.extend(["", "## External Required", ""])
    lines.extend(f"- `{item}`" for item in payload["external_required"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    payload = build_report_payload()
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "live_safety_evidence_report: "
        f"failures={len(payload['failures'])} "
        f"external_required={len(payload['external_required'])} "
        f"private_live={payload['private_live_decision']}"
    )
    if args.strict and payload["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
