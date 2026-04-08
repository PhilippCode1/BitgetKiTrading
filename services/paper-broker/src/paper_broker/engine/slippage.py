from __future__ import annotations

from decimal import Decimal


def walk_asks_fill(
    asks: list[tuple[Decimal, Decimal]], qty: Decimal
) -> tuple[Decimal, Decimal, bool]:
    """
    Market Buy: konsumiert Asks aufsteigend.
    Gibt (durchschnittspreis_gewichtet, gefuellte_menge, vollstaendig) zurueck.
    """
    remaining = qty
    cost = Decimal("0")
    filled = Decimal("0")
    for price, size in asks:
        if remaining <= 0:
            break
        take = min(remaining, size)
        cost += take * price
        filled += take
        remaining -= take
    if filled <= 0:
        return Decimal("0"), Decimal("0"), False
    avg = cost / filled
    return avg, filled, remaining <= 0


def walk_bids_fill(
    bids: list[tuple[Decimal, Decimal]], qty: Decimal
) -> tuple[Decimal, Decimal, bool]:
    """Market Sell: konsumiert Bids absteigend (erst hoechster Bid)."""
    remaining = qty
    cost = Decimal("0")
    filled = Decimal("0")
    for price, size in bids:
        if remaining <= 0:
            break
        take = min(remaining, size)
        cost += take * price
        filled += take
        remaining -= take
    if filled <= 0:
        return Decimal("0"), Decimal("0"), False
    avg = cost / filled
    return avg, filled, remaining <= 0


def synthetic_depth_from_best(
    *,
    best_bid: Decimal,
    best_ask: Decimal,
    levels: int,
    qty_per_level: Decimal,
    price_step: Decimal,
    side_for_fill: str,
) -> list[tuple[Decimal, Decimal]]:
    """
    Erzeugt deterministische Tiefe fuer SIM ohne Orderbuch-TSDB.
    side_for_fill: 'buy' -> asks; 'sell' -> bids
    """
    out: list[tuple[Decimal, Decimal]] = []
    if side_for_fill.lower() == "buy":
        p = best_ask
        for _ in range(levels):
            out.append((p, qty_per_level))
            p = p + price_step
    else:
        p = best_bid
        for _ in range(levels):
            out.append((p, qty_per_level))
            p = p - price_step
            if p <= 0:
                break
    return out


def apply_slippage_bps(mid: Decimal, bps: Decimal, side: str) -> Decimal:
    """Fallback: buy teurer, sell guenstiger."""
    factor = bps / Decimal("10000")
    if side.lower() == "buy":
        return mid * (Decimal("1") + factor)
    return mid * (Decimal("1") - factor)
