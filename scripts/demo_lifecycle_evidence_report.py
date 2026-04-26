#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


@dataclass
class DemoLifecycleEvidence:
    lifecycle_status: str
    demo_evidence_stage: str
    blockers: list[str]
    checks: dict[str, Any]
    live_trading_allowed: bool
    private_live_allowed: bool
    full_autonomous_live: bool
    live_verified: bool


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _pick(*names: str) -> dict[str, Any] | None:
    for name in names:
        payload = _load_json(REPORTS / name)
        if payload is not None:
            return payload
    return None


def build_lifecycle_evidence() -> DemoLifecycleEvidence:
    trading = _pick("demo_trading_evidence_DEMO_VERIFIED.json", "demo_trading_evidence.json")
    close_rep = _pick("demo_reconcile_evidence_CLOSE_VERIFIED.json", "demo_reconcile_evidence.json")
    clean_rep = _pick("demo_reconcile_evidence_CLEAN.json", "demo_reconcile_evidence.json")
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    demo_trading_archive_missing = _load_json(REPORTS / "demo_trading_evidence_DEMO_VERIFIED.json") is None
    demo_readiness_ok = bool(trading and str(trading.get("checks", {}).get("private_readonly_result") or "") != "not_run")
    demo_order_verified = bool(trading and str(trading.get("result") or "") == "DEMO_VERIFIED")
    demo_position_detected = bool(
        close_rep and str(close_rep.get("checks", {}).get("detected_position_side") or "") in ("long", "short")
    )
    demo_close_verified = bool(close_rep and str(close_rep.get("reconcile_status") or "") == "CLOSE_VERIFIED")
    final_reconcile_clean = bool(clean_rep and str(clean_rep.get("reconcile_status") or "") == "CLEAN")
    clean_positions_zero = str(clean_rep.get("checks", {}).get("positions_count") or "") == "0" if clean_rep else False
    clean_open_orders_zero = str(clean_rep.get("checks", {}).get("open_orders_count") or "") == "0" if clean_rep else False
    clean_history_ge_2 = False
    if clean_rep:
        try:
            clean_history_ge_2 = int(str(clean_rep.get("checks", {}).get("order_history_count") or "0")) >= 2
        except Exception:
            clean_history_ge_2 = False
    clean_live_blocked = bool(
        clean_rep
        and str(clean_rep.get("checks", {}).get("live_trading_allowed") or "false").lower() == "false"
        and str(clean_rep.get("checks", {}).get("private_live_allowed") or "false").lower() == "false"
    )
    demo_order_inferred = bool(
        demo_trading_archive_missing
        and demo_close_verified
        and final_reconcile_clean
        and clean_positions_zero
        and clean_open_orders_zero
        and clean_history_ge_2
        and clean_live_blocked
    )
    if demo_order_inferred:
        demo_order_verified = True

    checks["demo_readiness_ok"] = str(demo_readiness_ok).lower()
    checks["demo_order_verified"] = str(demo_order_verified).lower()
    checks["demo_position_detected"] = str(demo_position_detected).lower()
    checks["demo_close_verified"] = str(demo_close_verified).lower()
    checks["final_reconcile_clean"] = str(final_reconcile_clean).lower()
    checks["demo_trading_archive_missing"] = str(demo_trading_archive_missing).lower()
    checks["demo_order_verified_source"] = (
        "inferred_from_close_verified_and_clean_history" if demo_order_inferred else "trading_report"
    )
    checks["live_trading_allowed"] = "false"
    checks["private_live_allowed"] = "false"
    checks["full_autonomous_live"] = "false"
    checks["live_verified"] = "false"

    if not trading and not close_rep and not clean_rep:
        lifecycle_status = "NOT_ENOUGH_EVIDENCE"
        blockers.append("Demo-Lifecycle-Reports fehlen.")
    elif demo_order_verified and demo_position_detected and demo_close_verified and final_reconcile_clean:
        lifecycle_status = "DEMO_LIFECYCLE_VERIFIED"
    elif trading and (close_rep or clean_rep):
        lifecycle_status = "DEMO_PARTIAL"
        if not demo_close_verified:
            blockers.append("Demo-Close nicht als CLOSE_VERIFIED nachgewiesen.")
        if not final_reconcile_clean:
            blockers.append("Finaler Reconcile CLEAN nicht nachgewiesen.")
    elif trading and not demo_order_verified:
        lifecycle_status = "FAILED"
        blockers.append("Demo-Order-Smoke nicht als DEMO_VERIFIED nachgewiesen.")
    else:
        lifecycle_status = "NOT_ENOUGH_EVIDENCE"
        if not demo_close_verified:
            blockers.append("Close-Verifikation fehlt.")
        if not final_reconcile_clean:
            blockers.append("CLEAN-Verifikation fehlt.")

    stage = "implemented"
    if demo_readiness_ok:
        stage = "demo_ready"
    if demo_order_verified:
        stage = "demo_order_verified"
    if demo_position_detected:
        stage = "demo_reconcile_verified"
    if demo_close_verified:
        stage = "demo_close_verified"
    if lifecycle_status == "DEMO_LIFECYCLE_VERIFIED":
        stage = "demo_lifecycle_verified"

    return DemoLifecycleEvidence(
        lifecycle_status=lifecycle_status,
        demo_evidence_stage=stage,
        blockers=blockers,
        checks=checks,
        live_trading_allowed=False,
        private_live_allowed=False,
        full_autonomous_live=False,
        live_verified=False,
    )


def to_markdown(rep: DemoLifecycleEvidence) -> str:
    lines = [
        "# Demo Lifecycle Evidence Report",
        "",
        f"- lifecycle_status: `{rep.lifecycle_status}`",
        f"- demo_evidence_stage: `{rep.demo_evidence_stage}`",
        f"- live_trading_allowed: `{str(rep.live_trading_allowed).lower()}`",
        f"- private_live_allowed: `{str(rep.private_live_allowed).lower()}`",
        f"- full_autonomous_live: `{str(rep.full_autonomous_live).lower()}`",
        f"- live_verified: `{str(rep.live_verified).lower()}`",
        "",
        "## Checks",
        *[f"- `{k}`: `{v}`" for k, v in rep.checks.items()],
        "",
        "## Blocker",
        *([f"- {b}" for b in rep.blockers] if rep.blockers else ["- keine"]),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-md", type=Path, default=Path("reports/demo_lifecycle_evidence.md"))
    p.add_argument("--output-json", type=Path, default=Path("reports/demo_lifecycle_evidence.json"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    rep = build_lifecycle_evidence()
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(to_markdown(rep), encoding="utf-8")
    args.output_json.write_text(json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"demo_lifecycle_evidence: lifecycle_status={rep.lifecycle_status} stage={rep.demo_evidence_stage}")
    return 1 if rep.lifecycle_status in ("FAILED", "NOT_ENOUGH_EVIDENCE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
