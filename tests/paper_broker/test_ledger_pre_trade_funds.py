from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAPER_SRC = ROOT / "services" / "paper-broker" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (ROOT, PAPER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from paper_broker.exceptions import InsufficientPaperFundsException
from paper_broker.storage import repo_account_ledger


def test_assert_sufficient_paper_cash_dod_1m_notional_vs_10k_balance() -> None:
    """
    DoD: 1.000.000 USDT notional (Initial Margin) bei 10.000 USDT verfügbarem
    Guthaben muss mit InsufficientPaperFundsException scheitern.
    """
    with pytest.raises(InsufficientPaperFundsException) as ei:
        repo_account_ledger.assert_sufficient_paper_cash(
            available_cash_usdt=Decimal("10000"),
            initial_margin_usdt=Decimal("1000000"),
            order_fee_usdt=Decimal("0"),
        )
    ex = ei.value
    assert ex.available_usdt is not None and ex.required_usdt is not None
    assert ex.available_usdt < ex.required_usdt
