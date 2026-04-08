from __future__ import annotations

from decimal import Decimal


def price_to_str(p: Decimal) -> str:
    s = format(p, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"
