from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyCenterSnapshot:
    reconcile_status: str
    kill_switch_active: bool
    safety_latch_active: bool
    exchange_truth_status: str
    backend_connected: bool


def live_blocked_by_safety_center(snapshot: SafetyCenterSnapshot) -> bool:
    critical_unknown = snapshot.reconcile_status in {"unknown", "stale", "fail"} or snapshot.exchange_truth_status in {
        "unknown",
        "stale",
        "fehlt",
        "not_checked",
    }
    if critical_unknown:
        return True
    if snapshot.kill_switch_active or snapshot.safety_latch_active:
        return True
    if not snapshot.backend_connected:
        return True
    return False


def emergency_flatten_is_reduce_only(*, reduce_only: bool, requested_qty: float, position_qty: float) -> bool:
    if not reduce_only:
        return False
    if requested_qty <= 0 or position_qty <= 0:
        return False
    return requested_qty <= position_qty


def contains_secret_like_text(text: str) -> bool:
    lowered = text.lower()
    bad_tokens = ("api_key", "secret", "token", "passphrase", "password")
    return any(token in lowered for token in bad_tokens)
