from __future__ import annotations

from decimal import Decimal

from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry


def _d(x: object | None) -> Decimal | None:
    if x in (None, ""):
        return None
    try:
        v = Decimal(str(x))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return v


def validate_paper_base_order_qty(
    *,
    qty: Decimal,
    mark_or_fill_price: Decimal,
    order_type: str,
    entry: BitgetInstrumentCatalogEntry,
) -> None:
    """
    Menge muss exakt am Lot-Step (quantity_step) liegen, ohne implizite Rundung;
    zusaetzlich Min-Notional, Min/Max-Menge.
    """
    if qty is None or qty <= 0:
        raise ValueError("paper_order_invalid_qty")
    if mark_or_fill_price <= 0:
        raise ValueError("paper_order_invalid_price")
    step = _d(entry.quantity_step)
    if step is not None and step > 0:
        # Keine implizite Rundung — wie ungueltiger Kontrakt auf der Exchange
        if (qty // step) * step != qty:
            raise ValueError(
                f"paper_order_qty_lot_mismatch: {qty=}, {step=}, "
                f"quantity_precision={entry.quantity_precision}"
            )
    if entry.quantity_precision is not None and int(entry.quantity_precision) >= 0:
        max_places = int(entry.quantity_precision)
        q2 = qty.quantize(Decimal(1) / (Decimal(10) ** max_places))
        if q2 != qty:
            raise ValueError(
                f"paper_order_qty_precision_violation: {qty=}, {max_places=}"
            )
    qmin = _d(entry.quantity_min)
    if qmin is not None and qty < qmin:
        raise ValueError("paper_order_qty_below_minimum")
    is_m = (order_type or "") == "market"
    omax = _d(
        entry.market_order_quantity_max if is_m else entry.quantity_max
    )
    if omax is not None and omax > 0 and qty > omax:
        raise ValueError("paper_order_qty_above_maximum")
    mnq = _d(entry.min_notional_quote)
    if mnq is not None and mnq > 0:
        notional = abs(qty * mark_or_fill_price)
        if notional < mnq:
            raise ValueError("paper_order_notional_below_minimum")


__all__ = ["validate_paper_base_order_qty"]
