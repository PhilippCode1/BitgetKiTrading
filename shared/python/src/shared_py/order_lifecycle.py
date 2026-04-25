from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

OrderLifecycleState = Literal[
    "candidate",
    "preflight_passed",
    "owner_released",
    "submit_prepared",
    "submit_attempted",
    "exchange_acknowledged",
    "exchange_rejected",
    "unknown_submit_state",
    "reconcile_required",
    "open",
    "partially_filled",
    "filled",
    "cancel_requested",
    "canceled",
    "replace_requested",
    "replaced",
    "reduce_only_exit_requested",
    "emergency_flatten_requested",
    "closed",
    "failed",
    "blocked",
]


@dataclass(frozen=True)
class OrderSubmitContext:
    execution_id: str | None
    idempotency_key: str | None
    client_order_id: str | None
    known_client_order_ids: set[str]
    previous_state: OrderLifecycleState
    submit_result: Literal["ack", "reject", "timeout", "db_failure_after_submit", "unknown"]


def build_client_order_id(*, execution_id: str, symbol: str, nonce: str) -> str:
    base = f"{execution_id}:{symbol}:{nonce}"
    digest = sha256(base.encode("utf-8")).hexdigest()[:18]
    return f"cid_{digest}"


def validate_order_lifecycle_transition(*, previous: OrderLifecycleState, new: OrderLifecycleState) -> bool:
    allowed: dict[OrderLifecycleState, set[OrderLifecycleState]] = {
        "candidate": {"preflight_passed", "blocked"},
        "preflight_passed": {"owner_released", "blocked"},
        "owner_released": {"submit_prepared", "blocked"},
        "submit_prepared": {"submit_attempted", "blocked"},
        "submit_attempted": {"exchange_acknowledged", "exchange_rejected", "unknown_submit_state", "reconcile_required"},
        "exchange_acknowledged": {"open", "partially_filled", "filled", "cancel_requested", "replace_requested"},
        "open": {"partially_filled", "filled", "cancel_requested", "replace_requested", "reduce_only_exit_requested", "emergency_flatten_requested"},
        "partially_filled": {"filled", "cancel_requested", "reduce_only_exit_requested", "emergency_flatten_requested"},
        "cancel_requested": {"canceled", "failed"},
        "replace_requested": {"replaced", "failed"},
        "reduce_only_exit_requested": {"closed", "failed"},
        "emergency_flatten_requested": {"closed", "failed"},
        "unknown_submit_state": {"reconcile_required", "blocked"},
        "reconcile_required": {"blocked", "open", "canceled"},
        "exchange_rejected": {"failed"},
        "filled": {"closed"},
        "replaced": {"open"},
        "canceled": {"closed"},
        "failed": set(),
        "blocked": set(),
        "closed": set(),
    }
    return new in allowed.get(previous, set())


def duplicate_order_blocks_submit(*, client_order_id: str | None, known_client_order_ids: set[str]) -> bool:
    if not client_order_id:
        return False
    return client_order_id in known_client_order_ids


def submit_result_requires_reconcile(result: Literal["ack", "reject", "timeout", "db_failure_after_submit", "unknown"]) -> bool:
    return result in {"timeout", "db_failure_after_submit", "unknown"}


def evaluate_submit_safety(ctx: OrderSubmitContext) -> tuple[OrderLifecycleState, list[str]]:
    reasons: list[str] = []
    if not ctx.execution_id:
        reasons.append("execution_id_fehlt")
    if not ctx.idempotency_key and not ctx.client_order_id:
        reasons.append("idempotency_fehlt")
    if duplicate_order_blocks_submit(client_order_id=ctx.client_order_id, known_client_order_ids=ctx.known_client_order_ids):
        reasons.append("duplicate_client_order_id")
    if ctx.previous_state == "unknown_submit_state":
        reasons.append("unknown_submit_state_blockiert_neue_openings")
    if ctx.previous_state == "reconcile_required":
        reasons.append("retry_ohne_reconcile_verboten")
    if reasons:
        return "blocked", reasons

    if ctx.submit_result == "ack":
        return "exchange_acknowledged", []
    if ctx.submit_result == "reject":
        return "exchange_rejected", ["exchange_reject"]
    if ctx.submit_result == "timeout":
        return "unknown_submit_state", ["submit_timeout_unknown_state"]
    if ctx.submit_result == "db_failure_after_submit":
        return "reconcile_required", ["db_failure_reconcile_required"]
    return "unknown_submit_state", ["unknown_submit_response"]


def build_order_lifecycle_audit_payload(
    *,
    previous_state: OrderLifecycleState,
    new_state: OrderLifecycleState,
    reasons: list[str],
    execution_id: str | None,
    client_order_id: str | None,
) -> dict[str, object]:
    return {
        "previous_state": previous_state,
        "new_state": new_state,
        "reasons": reasons,
        "execution_id_present": bool(execution_id),
        "client_order_id_present": bool(client_order_id),
    }
