from __future__ import annotations

from math import floor
from typing import Any, Mapping

LEVERAGE_ALLOCATOR_VERSION = "int-leverage-v1"
MIN_LEVERAGE = 7
MAX_LEVERAGE = 75


def normalize_leverage_cap(
    value: Any,
    *,
    max_leverage: int = MAX_LEVERAGE,
) -> int | None:
    if value in (None, ""):
        return None
    try:
        cap = int(floor(float(value)))
    except (TypeError, ValueError):
        return None
    return max(0, min(int(max_leverage), cap))


def allocate_integer_leverage(
    *,
    requested_leverage: Any,
    caps: Mapping[str, Any],
    min_leverage: int = MIN_LEVERAGE,
    max_leverage: int = MAX_LEVERAGE,
    blocked_reason: str = "allowed_leverage_below_minimum",
) -> dict[str, Any]:
    requested = normalize_leverage_cap(requested_leverage, max_leverage=max_leverage)
    if requested is None:
        requested = int(max_leverage)

    normalized_caps: dict[str, int] = {}
    for name, raw_value in caps.items():
        normalized = normalize_leverage_cap(raw_value, max_leverage=max_leverage)
        if normalized is None:
            continue
        normalized_caps[str(name)] = normalized

    allowed = requested
    if normalized_caps:
        allowed = min(allowed, *normalized_caps.values())

    binding_cap_names = sorted(
        [name for name, value in normalized_caps.items() if value == allowed]
    )
    cap_reasons = [f"{name}_binding" for name in binding_cap_names]
    recommended = allowed if allowed >= min_leverage else None
    if recommended is None:
        cap_reasons.append(blocked_reason)

    return {
        "policy_version": LEVERAGE_ALLOCATOR_VERSION,
        "requested_leverage": requested,
        "allowed_leverage": allowed,
        "recommended_leverage": recommended,
        "binding_cap_names": binding_cap_names,
        "cap_reasons_json": cap_reasons,
        "caps": normalized_caps,
        "blocked_reason": blocked_reason if recommended is None else None,
    }
