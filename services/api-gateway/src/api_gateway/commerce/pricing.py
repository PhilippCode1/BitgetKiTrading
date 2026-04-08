"""Transparente List-Preisberechnung — feste Formeln, kein versteckter Multiplikator."""

from __future__ import annotations

from decimal import Decimal


def llm_tokens_line_total_usd(*, token_count: float, usd_per_1k_tokens: Decimal) -> Decimal:
    """USD = (tokens / 1000) * list_price_per_1k."""
    qty = Decimal(str(token_count))
    if qty < 0:
        raise ValueError("token_count must be >= 0")
    return (qty / Decimal("1000")) * usd_per_1k_tokens
