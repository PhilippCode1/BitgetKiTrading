#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.exit_safety import ReduceOnlyExitRequest, build_exit_block_reasons_de, validate_emergency_flatten_request, validate_reduce_only_exit  # noqa: E402
from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety  # noqa: E402


def _simulated_report() -> str:
    lines = ["# Order-Lifecycle-Safety-Drill", ""]

    ok_state, ok_reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-a", set(), "submit_prepared", "ack")
    )
    timeout_state, timeout_reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-2", "idem-2", "cid-b", set(), "submit_prepared", "timeout")
    )
    duplicate_state, duplicate_reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-3", "idem-3", "cid-dup", {"cid-dup"}, "submit_prepared", "ack")
    )
    reduce_reasons = validate_reduce_only_exit(
        ReduceOnlyExitRequest("BTCUSDT", 0.2, 1.0, True, [50.0, 50.0], 0.1, True, None, False)
    )
    emergency_reasons = validate_emergency_flatten_request(
        ReduceOnlyExitRequest("BTCUSDT", 1.2, 1.0, True, [100.0], 0.1, False, "kill_switch_active", True)
    )

    lines.extend(
        [
            "## successful submit",
            f"- state: {ok_state}",
            f"- reasons: {ok_reasons or ['keine']}",
            "",
            "## timeout unknown submit state",
            f"- state: {timeout_state}",
            f"- reasons: {timeout_reasons}",
            "",
            "## duplicate retry attempt",
            f"- state: {duplicate_state}",
            f"- reasons: {duplicate_reasons}",
            "",
            "## reduce-only exit",
            f"- reasons: {build_exit_block_reasons_de(reduce_reasons)}",
            "",
            "## emergency flatten simulation",
            f"- reasons: {build_exit_block_reasons_de(emergency_reasons)}",
            "",
            "## cancel/replace safety",
            "- duplicate order id in cancel/replace -> block (simuliert)",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Order-Lifecycle/Exit-Safety-Drill")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", default="simulated")
    parser.add_argument("--output-md", default="reports/order_lifecycle_safety_drill_sample.md")
    args = parser.parse_args()
    if args.mode != "simulated":
        raise SystemExit("Nur --mode simulated ist lokal erlaubt.")
    if args.dry_run:
        print("order_lifecycle_safety_drill: dry-run ok (mode=simulated)")
        return 0
    out = Path(args.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_simulated_report(), encoding="utf-8")
    print(f"order_lifecycle_safety_drill: ok (mode=simulated, output={out.as_posix()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
