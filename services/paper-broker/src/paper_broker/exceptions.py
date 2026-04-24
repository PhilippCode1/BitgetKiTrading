from __future__ import annotations

from decimal import Decimal


class InsufficientPaperFundsException(ValueError):
    """
    Nicht genug verfuegbare Paper-Quote (Konten-Cash) fuer Margin + Gebaehr der Order.
    """

    def __init__(
        self,
        message: str = "insufficient_paper_funds",
        *,
        available_usdt: Decimal | None = None,
        required_usdt: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.available_usdt = available_usdt
        self.required_usdt = required_usdt
