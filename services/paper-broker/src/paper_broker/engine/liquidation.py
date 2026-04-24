from __future__ import annotations

from decimal import Decimal


def unrealized_pnl(side: str, qty: Decimal, entry_avg: Decimal, mark: Decimal) -> Decimal:
    s = side.lower()
    if s == "long":
        return (mark - entry_avg) * qty
    if s == "short":
        return (entry_avg - mark) * qty
    raise ValueError(f"unknown side {side}")


def realized_pnl_liquidation_fill(
    side: str, qty: Decimal, entry_avg: Decimal, liq_fill: Decimal
) -> Decimal:
    """
    P&L bei sofortigem Abwicklungspreis (Stress-Book) statt Mark-Trigger.
    """
    return unrealized_pnl(side, qty, entry_avg, liq_fill)


def should_liquidate_approx(
    *,
    isolated_margin: Decimal,
    qty: Decimal,
    entry_avg: Decimal,
    mark: Decimal,
    side: str,
    accrued_fees: Decimal,
    net_funding_ledger: Decimal,
    maintenance_margin_rate: Decimal,
    liq_fee_buffer_usdt: Decimal,
) -> bool:
    """
    Approximation (nicht Bitget-1:1): siehe docs/paper_broker.md.
    equity = isolated_margin + unrealized_pnl - accrued_fees + net_funding_ledger
    (net_funding_ledger = Summe gebuchter funding_usdt; negativ wenn netto gezahlt.)
    """
    upnl = unrealized_pnl(side, qty, entry_avg, mark)
    equity = isolated_margin + upnl - accrued_fees + net_funding_ledger
    notional = abs(qty * mark)
    threshold = notional * maintenance_margin_rate + liq_fee_buffer_usdt
    return equity <= threshold
