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

from shared_py.reconcile_truth import (  # noqa: E402
    ReconcileTruthContext,
    build_reconcile_drift_reasons_de,
    evaluate_reconcile_truth,
)


def _build_simulated_cases() -> list[tuple[str, ReconcileTruthContext]]:
    base = dict(
        global_status="ok",
        per_asset_status={"BTCUSDT": "ok", "ETHUSDT": "ok"},
        reconcile_fresh=True,
        exchange_reachable=True,
        auth_ok=True,
        unknown_order_state=False,
        position_mismatch=False,
        fill_mismatch=False,
        exchange_order_missing=False,
        local_order_missing=False,
        safety_latch_active=False,
    )
    return [
        ("exchange_order_missing", ReconcileTruthContext(**{**base, "exchange_order_missing": True, "global_status": "exchange_order_missing"})),
        ("local_order_missing", ReconcileTruthContext(**{**base, "local_order_missing": True, "global_status": "local_order_missing"})),
        ("position_mismatch", ReconcileTruthContext(**{**base, "position_mismatch": True, "global_status": "position_mismatch"})),
        ("stale_reconcile", ReconcileTruthContext(**{**base, "reconcile_fresh": False, "global_status": "stale"})),
        ("unknown_order_state", ReconcileTruthContext(**{**base, "unknown_order_state": True, "global_status": "unknown_order_state"})),
        ("safety_latch_required", ReconcileTruthContext(**{**base, "fill_mismatch": True, "global_status": "fill_mismatch"})),
    ]


def _report_markdown() -> str:
    lines = ["# Reconcile-Truth-Drill (simulated)", ""]
    for name, ctx in _build_simulated_cases():
        decision = evaluate_reconcile_truth(ctx)
        reasons = build_reconcile_drift_reasons_de(decision)
        lines.extend(
            [
                f"## Szenario: {name}",
                f"- Ergebnisstatus: {decision.status}",
                f"- Reconcile required: {decision.reconcile_required}",
                f"- Safety-Latch required: {decision.safety_latch_required}",
                f"- Main-Console-Status: {'BLOCKIERT' if decision.blocking_reasons else 'WARNUNG/OK'}",
                f"- Gruende: {', '.join(reasons)}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile/Exchange-Truth Drill")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", default="simulated")
    parser.add_argument("--output-md", default="reports/reconcile_truth_drill_sample.md")
    args = parser.parse_args()
    if args.mode != "simulated":
        raise SystemExit("Nur --mode simulated ist lokal erlaubt.")
    if args.dry_run:
        print("reconcile_truth_drill: dry-run ok (mode=simulated)")
        return 0
    out = Path(args.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_report_markdown(), encoding="utf-8")
    print(f"reconcile_truth_drill: ok (mode=simulated, output={out.as_posix()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
