from __future__ import annotations

from decimal import Decimal


def calc_funding_usdt(position_value: Decimal, funding_rate: Decimal, side: str) -> Decimal:
    """
    Bitget-Logik vereint: raw = position_value * funding_rate.
    Long: -raw (bei positivem Rate zahlt Long). Short: +raw.
    Rueckgabe aus Sicht dieser Position (negativ = zahlt).
    """
    raw = position_value * funding_rate
    s = side.lower()
    return -raw if s == "long" else raw
