from __future__ import annotations

from decimal import Decimal
from typing import Any


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


def _d01(x: Any) -> Decimal:
    if x in (None, ""):
        return Decimal("0")
    try:
        v = Decimal(str(x))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0")
    if v < 0:
        return Decimal("0")
    if v > 1:
        return Decimal("1")
    return v


def volatility_effective_slippage_bps(
    base_bps: Decimal,
    *,
    tick_payload: dict[str, Any] | None,
    bps_per_atr_0_1: Decimal,
    bps_per_vpin_0_1: Decimal,
) -> Decimal:
    """
    ATR% / VPIN (market-stream) skalieren Slippage-Bps; Tick z. B. atrp_14, vpin_0_1 in [0,1].
    bps_per_*: Zusatzbps pro 0.1 Einheit des normalisierten Signals.
    """
    if not tick_payload:
        return base_bps
    pl = {str(k).lower(): v for k, v in tick_payload.items()}
    raw_atr = pl.get("atrp_14")
    if raw_atr in (None, ""):
        raw_atr = pl.get("atrp")
    if raw_atr in (None, ""):
        raw_atr = pl.get("atr_14")
    atr_e = _d01(raw_atr)
    raw_v = pl.get("vpin_0_1")
    if raw_v in (None, ""):
        raw_v = pl.get("vpin")
    v_e = _d01(raw_v)
    return (
        base_bps
        + bps_per_atr_0_1 * (atr_e * Decimal(10))
        + bps_per_vpin_0_1 * (v_e * Decimal(10))
    )


def worst_price_sell_liquidation_top_bids(
    bids: list[tuple[Decimal, Decimal]],
    n: int = 5,
) -> Decimal | None:
    """Long-Liquidation: alle Verkaeufe in Bids; schlechtester Preis = tiefstes der Top-n."""
    if not bids:
        return None
    m = min(int(n), len(bids))
    return min(bids[i][0] for i in range(m))


def worst_price_buy_liquidation_top_asks(
    asks: list[tuple[Decimal, Decimal]],
    n: int = 5,
) -> Decimal | None:
    """Short-Liquidation: Kaeufe in Asks; schlechtester = hoechstes der Top-n."""
    if not asks:
        return None
    m = min(int(n), len(asks))
    return max(asks[i][0] for i in range(m))
