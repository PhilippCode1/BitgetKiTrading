"""
Deterministische Boersen-/Ausfuehrungs-Safety-Checks (ohne LLM).
Family-agnostisch: arbeitet auf Dezimalpreisen/-mengen aus Public-Snapshot + Order-Kontext.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _d(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def spread_half_bps(*, bid: Decimal | None, ask: Decimal | None) -> Decimal | None:
    if bid is None or ask is None or bid <= 0 or ask < bid:
        return None
    mid = (bid + ask) / Decimal("2")
    if mid <= 0:
        return None
    return ((ask - bid) / Decimal("2")) / mid * Decimal("10000")


def market_spread_slippage_cap_reasons(
    *,
    side: str,
    bid: Decimal | None,
    ask: Decimal | None,
    max_spread_half_bps: Decimal | None,
) -> list[str]:
    """
    Blockt Market-Orders, wenn die halbe Spread-Breite (in bps zum Mid) den Cap uebersteigt
    (Proxy fuer schlechte Ausfuehrbarkeit / zu breites Buch).
    """
    _ = side
    if max_spread_half_bps is None or max_spread_half_bps <= 0:
        return []
    sh = spread_half_bps(bid=bid, ask=ask)
    if sh is None:
        return ["execution_guard_spread_snapshot_incomplete"]
    if sh > max_spread_half_bps:
        return [f"execution_guard_spread_half_bps_exceeds_cap:{sh:.4f}>{max_spread_half_bps}"]
    return []


def preset_stop_distance_floor_reasons(
    *,
    stop_price: Decimal | None,
    reference_price: Decimal | None,
    min_distance_bps: Decimal | None,
) -> list[str]:
    """Mindestabstand Stop zu Referenz (Mark/Mid) in bps — gap-to-stop / zu enger Stop."""
    if min_distance_bps is None or min_distance_bps <= 0:
        return []
    if stop_price is None or reference_price is None or reference_price <= 0 or stop_price <= 0:
        return []
    dist_bps = abs(reference_price - stop_price) / reference_price * Decimal("10000")
    if dist_bps < min_distance_bps:
        return [f"execution_guard_preset_stop_distance_bps_below_floor:{dist_bps:.4f}<{min_distance_bps}"]
    return []


def preset_stop_vs_spread_reasons(
    *,
    stop_price: Decimal | None,
    reference_price: Decimal | None,
    bid: Decimal | None,
    ask: Decimal | None,
    min_stop_to_spread_mult: Decimal | None,
) -> list[str]:
    """
    Stop-to-Spread: |ref-stop| muss >= min_mult * Spread sein (Spread = ask-bid).
    """
    if min_stop_to_spread_mult is None or min_stop_to_spread_mult <= 0:
        return []
    if stop_price is None or reference_price is None:
        return []
    if bid is None or ask is None or ask < bid or bid <= 0:
        return []
    spread = ask - bid
    if spread <= 0:
        return []
    dist = abs(reference_price - stop_price)
    need = spread * min_stop_to_spread_mult
    if dist < need:
        return [
            "execution_guard_preset_stop_too_close_to_spread:"
            f"dist={dist} need>={need} mult={min_stop_to_spread_mult}"
        ]
    return []


def reduce_only_position_consistency_reasons(
    *,
    reduce_only: bool,
    order_side: str,
    position_net_base: Decimal | None,
    require_known_position: bool,
) -> list[str]:
    if not reduce_only:
        return []
    side = str(order_side or "").strip().lower()
    if position_net_base is None:
        if require_known_position:
            return ["execution_guard_position_unknown_for_reduce_only"]
        return []
    if position_net_base == 0:
        return ["execution_guard_no_position_for_reduce_only"]
    if position_net_base > 0 and side != "sell":
        return ["execution_guard_reduce_only_side_mismatch_long"]
    if position_net_base < 0 and side != "buy":
        return ["execution_guard_reduce_only_side_mismatch_short"]
    return []


def replace_size_safety_reasons(
    *,
    existing_reduce_only: bool,
    old_size: Decimal | None,
    new_size: Decimal | None,
) -> list[str]:
    """Cancel/Replace: keine Groessen-Erhoehung bei reduce-only."""
    if not existing_reduce_only or old_size is None or new_size is None:
        return []
    if new_size > old_size:
        return ["execution_guard_replace_increase_size_blocked_reduce_only"]
    return []
