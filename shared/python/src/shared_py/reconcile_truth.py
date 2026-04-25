from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

ReconcileStatus = Literal[
    "ok",
    "warning",
    "stale",
    "drift_detected",
    "exchange_unreachable",
    "auth_failed",
    "rate_limited",
    "unknown_order_state",
    "local_order_missing",
    "exchange_order_missing",
    "position_mismatch",
    "fill_mismatch",
    "safety_latch_required",
    "blocked",
]


@dataclass(frozen=True)
class ReconcileTruthContext:
    global_status: ReconcileStatus
    per_asset_status: dict[str, ReconcileStatus]
    reconcile_fresh: bool
    exchange_reachable: bool
    auth_ok: bool
    unknown_order_state: bool
    position_mismatch: bool
    fill_mismatch: bool
    exchange_order_missing: bool
    local_order_missing: bool
    safety_latch_active: bool
    reduce_only_mode: bool = False
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class ReconcileTruthDecision:
    status: ReconcileStatus
    blocking_reasons: list[str]
    warning_reasons: list[str]
    reconcile_required: bool
    safety_latch_required: bool
    allows_next_gate_only: bool
    checked_at: str


_REASON_DE = {
    "reconcile_stale": "Reconcile ist stale.",
    "exchange_unreachable": "Exchange ist nicht erreichbar.",
    "auth_failed": "Exchange-Authentifizierung fehlgeschlagen.",
    "unknown_order_state": "Unklarer Order-Status vorhanden.",
    "position_mismatch": "Positionsabweichung zwischen lokal und Exchange erkannt.",
    "fill_mismatch": "Fill-Abweichung erkannt.",
    "exchange_order_missing": "Lokale offene Order fehlt auf der Exchange.",
    "local_order_missing": "Exchange-Order fehlt lokal.",
    "safety_latch_active": "Safety-Latch ist aktiv.",
}


def evaluate_reconcile_truth(context: ReconcileTruthContext) -> ReconcileTruthDecision:
    blocking: list[str] = []
    warning: list[str] = []
    reconcile_required = False
    safety_required = False

    if not context.reconcile_fresh or context.global_status == "stale":
        blocking.append("reconcile_stale")
    if not context.exchange_reachable or context.global_status == "exchange_unreachable":
        blocking.append("exchange_unreachable")
    if not context.auth_ok or context.global_status == "auth_failed":
        blocking.append("auth_failed")
    if context.unknown_order_state or context.global_status == "unknown_order_state":
        blocking.append("unknown_order_state")
    if context.position_mismatch or context.global_status == "position_mismatch":
        blocking.append("position_mismatch")
    if context.fill_mismatch or context.global_status == "fill_mismatch":
        warning.append("fill_mismatch")
        safety_required = True
        blocking.append("fill_mismatch")
    if context.exchange_order_missing or context.global_status == "exchange_order_missing":
        warning.append("exchange_order_missing")
        reconcile_required = True
    if context.local_order_missing or context.global_status == "local_order_missing":
        warning.append("local_order_missing")
        reconcile_required = True
    if context.safety_latch_active or context.global_status == "safety_latch_required":
        blocking.append("safety_latch_active")

    status: ReconcileStatus = "ok"
    if blocking:
        status = "blocked"
    elif reconcile_required or warning:
        status = "warning"

    return ReconcileTruthDecision(
        status=status,
        blocking_reasons=list(dict.fromkeys(blocking)),
        warning_reasons=list(dict.fromkeys(warning)),
        reconcile_required=reconcile_required,
        safety_latch_required=safety_required,
        allows_next_gate_only=(status == "ok"),
        checked_at=context.checked_at,
    )


def reconcile_requires_safety_latch(decision: ReconcileTruthDecision) -> bool:
    return decision.safety_latch_required or "fill_mismatch" in decision.blocking_reasons


def reconcile_truth_blocks_live(decision: ReconcileTruthDecision) -> bool:
    return len(decision.blocking_reasons) > 0


def build_reconcile_drift_reasons_de(decision: ReconcileTruthDecision) -> list[str]:
    reasons = decision.blocking_reasons or decision.warning_reasons
    if not reasons:
        return ["Reconcile OK: nur naechster Gate-Schritt erlaubt."]
    return [_REASON_DE.get(code, f"Unbekannter Reconcile-Grund: {code}") for code in reasons]


def build_reconcile_audit_payload(
    *,
    context: ReconcileTruthContext,
    decision: ReconcileTruthDecision,
) -> dict[str, object]:
    return {
        "checked_at": decision.checked_at,
        "status": decision.status,
        "blocking_reasons": decision.blocking_reasons,
        "warning_reasons": decision.warning_reasons,
        "reconcile_required": decision.reconcile_required,
        "safety_latch_required": decision.safety_latch_required,
        "per_asset_status": context.per_asset_status,
        "global_status": context.global_status,
        "reduce_only_mode": context.reduce_only_mode,
    }
