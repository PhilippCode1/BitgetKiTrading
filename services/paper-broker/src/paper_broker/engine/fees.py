from __future__ import annotations

from decimal import Decimal


def calc_transaction_fee_usdt(qty_base: Decimal, price: Decimal, fee_rate: Decimal) -> Decimal:
    """Bitget: fee = (qty * price) * fee_rate."""
    return (qty_base * price) * fee_rate


def order_notional_usdt(qty_base: Decimal, price: Decimal) -> Decimal:
    return qty_base * price
