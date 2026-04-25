#!/usr/bin/env python3
"""Simulated secret-rotation drill.

This script never reads, prints, or writes raw secret values. It operates only
on secret class names and static policy metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.secret_lifecycle import (  # noqa: E402
    all_secret_policies,
    build_secret_rotation_audit_payload,
)


def build_simulated_drill(as_of: datetime | None = None) -> dict[str, Any]:
    now = as_of or datetime.now(tz=UTC)
    expired_last_rotated = now - timedelta(days=400)
    compromised_last_rotated = now - timedelta(days=5)
    inventory = [asdict(policy) for policy in all_secret_policies()]
    expired = build_secret_rotation_audit_payload(
        "JWT_SECRET",
        owner="Platform Security",
        environment="production",
        reason="scheduled_expiry_drill",
        last_rotated_at=expired_last_rotated,
        as_of=now,
    )
    compromised = build_secret_rotation_audit_payload(
        "TELEGRAM_BOT_TOKEN",
        owner="Operator Communications / Security",
        environment="production",
        reason="simulated_compromise_drill",
        last_rotated_at=compromised_last_rotated,
        as_of=now,
    )
    plan = [
        "Freeze affected live-control path and confirm fail-closed state.",
        "Create replacement credential in the environment-specific secret store.",
        "Deploy secret reference version without printing raw values.",
        "Restart dependent services in dependency order.",
        "Run auth, health, reconcile, and operator-channel smoke checks.",
        "Revoke old credential and record audit evidence.",
    ]
    rollback = [
        "Keep old credential disabled; rollback only to previous secret reference if not compromised.",
        "If compromise is suspected, rollback is service config only, never old credential reuse.",
        "Keep live trading blocked until owner signs the post-drill status.",
    ]
    return {
        "generated_at": now.isoformat(),
        "mode": "simulated",
        "raw_secret_values_included": False,
        "inventory_count": len(inventory),
        "inventory": inventory,
        "expired_secret": expired,
        "compromised_secret": compromised,
        "rotation_plan": plan,
        "service_restart_notes": [
            "Restart gateway/auth clients after JWT and internal API key rotation.",
            "Restart live-broker only after exchange credentials and risk gates are verified.",
            "Restart alert-engine after Telegram credential rotation and webhook verification.",
        ],
        "rollback": rollback,
        "go_no_go": "NO-GO for live money until real secret-store rotation evidence exists.",
    }


def render_markdown(drill: dict[str, Any]) -> str:
    expired = drill["expired_secret"]
    compromised = drill["compromised_secret"]
    lines = [
        "# Secrets Rotation Drill Report",
        "",
        f"- Generated at: `{drill['generated_at']}`",
        f"- Mode: `{drill['mode']}`",
        f"- Raw secret values included: `{str(drill['raw_secret_values_included']).lower()}`",
        f"- Inventory classes: `{drill['inventory_count']}`",
        "",
        "## Simulated Findings",
        "",
        f"- Expired class: `{expired['secret_id']}` (`expired={str(expired['expired']).lower()}`)",
        f"- Compromised class: `{compromised['secret_id']}` (`reason={compromised['reason']}`)",
        "",
        "## Rotation Plan",
        "",
    ]
    lines.extend(f"{idx}. {step}" for idx, step in enumerate(drill["rotation_plan"], 1))
    lines.extend(["", "## Service Restart Notes", ""])
    lines.extend(f"- {note}" for note in drill["service_restart_notes"])
    lines.extend(["", "## Rollback", ""])
    lines.extend(f"- {step}" for step in drill["rollback"])
    lines.extend(["", "## Go/No-Go", "", drill["go_no_go"], ""])
    return "\n".join(lines)


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print a safe drill summary.")
    parser.add_argument(
        "--mode",
        choices=("simulated",),
        default="simulated",
        help="Drill mode. Only static simulation is supported.",
    )
    parser.add_argument("--output-md", type=Path, help="Write a Markdown drill report.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args(argv)

    drill = build_simulated_drill()
    if args.output_md:
        _write_report(args.output_md, render_markdown(drill))

    if args.json:
        print(json.dumps(drill, indent=2, sort_keys=True))
        return 0

    if args.dry_run or not args.output_md:
        print("secrets_rotation_drill: simulated")
        print(f"inventory_classes={drill['inventory_count']}")
        print(f"expired_class={drill['expired_secret']['secret_id']}")
        print(f"compromised_class={drill['compromised_secret']['secret_id']}")
        print("raw_secret_values_included=false")
        print(drill["go_no_go"])
    else:
        print(f"secrets_rotation_drill: report written to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
