#!/usr/bin/env python3
"""Simulated live safety drill evidence, without exchange writes."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SafetyDrillEvidence:
    generated_at: str
    git_sha: str
    mode: str
    kill_switch_active: bool
    safety_latch_active: bool
    opening_order_blocked_by_kill_switch: bool
    opening_order_blocked_by_safety_latch: bool
    emergency_flatten_reduce_only: bool
    emergency_flatten_safe: bool
    audit_expected: bool
    alert_expected: bool
    go_no_go: str
    live_write_allowed: bool


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def simulate_safety_drill(mode: str) -> SafetyDrillEvidence:
    kill_switch_active = True
    safety_latch_active = True
    opening_blocked_ks = kill_switch_active
    opening_blocked_latch = safety_latch_active
    emergency_reduce_only = True
    emergency_safe = emergency_reduce_only and opening_blocked_ks and opening_blocked_latch
    audit_expected = True
    alert_expected = True
    go_no_go = "NO_GO" if opening_blocked_ks and opening_blocked_latch and emergency_safe else "FAIL"
    return SafetyDrillEvidence(
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha(),
        mode=mode,
        kill_switch_active=kill_switch_active,
        safety_latch_active=safety_latch_active,
        opening_order_blocked_by_kill_switch=opening_blocked_ks,
        opening_order_blocked_by_safety_latch=opening_blocked_latch,
        emergency_flatten_reduce_only=emergency_reduce_only,
        emergency_flatten_safe=emergency_safe,
        audit_expected=audit_expected,
        alert_expected=alert_expected,
        go_no_go=go_no_go,
        live_write_allowed=False,
    )


def evidence_to_markdown(evidence: SafetyDrillEvidence) -> str:
    return "\n".join(
        [
            "# Live Safety Drill Evidence",
            "",
            f"- Datum/Zeit: `{evidence.generated_at}`",
            f"- Git SHA: `{evidence.git_sha}`",
            f"- Modus: `{evidence.mode}`",
            f"- Kill-Switch aktiv: `{str(evidence.kill_switch_active).lower()}`",
            f"- Safety-Latch aktiv: `{str(evidence.safety_latch_active).lower()}`",
            f"- Opening Order blockiert: `{str(evidence.opening_order_blocked_by_kill_switch and evidence.opening_order_blocked_by_safety_latch).lower()}`",
            f"- Emergency-Flatten reduce-only: `{str(evidence.emergency_flatten_reduce_only).lower()}`",
            f"- Audit erwartet: `{str(evidence.audit_expected).lower()}`",
            f"- Alert erwartet: `{str(evidence.alert_expected).lower()}`",
            f"- Go/No-Go: `{evidence.go_no_go}`",
            f"- Live-Write erlaubt: `{str(evidence.live_write_allowed).lower()}`",
            "",
            "## Redacted JSON",
            "```json",
            json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=("simulated",), default="simulated")
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    mode = "dry-run" if args.dry_run else args.mode
    evidence = simulate_safety_drill(mode)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(evidence_to_markdown(evidence), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "live_safety_drill: "
            f"go_no_go={evidence.go_no_go} mode={evidence.mode} live_write_allowed=false"
        )
    return 0 if evidence.go_no_go == "NO_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
