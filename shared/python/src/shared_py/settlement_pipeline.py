"""
Profit-Fee-Settlement-Pipeline (Prompt 16): reine Zustandslogik ohne I/O.

Ausfuehrung ist **nicht** an eine Exchange-API gebunden; Terminalzustaende
``settled`` / ``failed`` / ``cancelled`` sind stopbar und idempotent behandelbar.
"""

from __future__ import annotations

from typing import Any

SETTLEMENT_PIPELINE_VERSION = "settlement-pipeline-v1"

# Erlaubte Zustandsuebergaenge: (status_von, aktion) -> status_nach
_TRANSITIONS: dict[tuple[str, str], str] = {
    ("pending_treasury", "treasury_approve"): "approved_for_payout",
    ("pending_treasury", "cancel"): "cancelled",
    ("pending_treasury", "fail"): "failed",
    ("approved_for_payout", "record_payout"): "payout_recorded",
    ("approved_for_payout", "cancel"): "cancelled",
    ("approved_for_payout", "fail"): "failed",
    ("payout_recorded", "confirm_settled"): "settled",
    ("payout_recorded", "cancel"): "cancelled",
    ("payout_recorded", "fail"): "failed",
}

_TERMINAL = frozenset({"settled", "cancelled", "failed"})


def settlement_pipeline_descriptor() -> dict[str, str]:
    return {"settlement_pipeline_version": SETTLEMENT_PIPELINE_VERSION}


def is_terminal_status(status: str) -> bool:
    return status in _TERMINAL


def next_status(current: str, action: str) -> str | None:
    return _TRANSITIONS.get((current, action))


def assert_transition_allowed(current: str, action: str) -> str:
    nxt = next_status(current, action)
    if nxt is None:
        raise ValueError(f"transition not allowed: {current!r} + {action!r}")
    return nxt


def initial_status(*, secondary_treasury_approval_required: bool) -> str:
    if secondary_treasury_approval_required:
        return "pending_treasury"
    return "approved_for_payout"


def public_audit_payload_trim(
    payload: dict[str, Any],
    *,
    max_keys: int = 32,
) -> dict[str, Any]:
    """Kleine defensive Kopie fuer Audit-JSON (keine grossen Blobs)."""
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(payload.items()):
        if i >= max_keys:
            break
        if v is None or isinstance(v, str | int | float | bool):
            out[str(k)[:64]] = v
        else:
            out[str(k)[:64]] = str(v)[:2000]
    return out
