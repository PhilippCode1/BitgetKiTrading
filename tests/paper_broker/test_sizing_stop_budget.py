from __future__ import annotations

from decimal import Decimal

import pytest

from paper_broker.config import PaperBrokerSettings
from paper_broker.strategy.sizing import qty_with_stop_budget


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> PaperBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    return PaperBrokerSettings()


def test_qty_stop_budget_scales_with_equity(settings: PaperBrokerSettings) -> None:
    sig = {"signal_class": "kern", "direction": "long", "expected_return_bps": 20.0}
    ctx = {"account_equity": "10000", "reference_price": "50000"}
    q = qty_with_stop_budget(settings, sig, "kern", context=ctx)
    base = Decimal(str(settings.strat_base_qty_btc))
    assert q > base
    assert q <= base * Decimal(str(settings.paper_stop_budget_qty_cap_mult))


def test_qty_falls_back_without_reference_price(settings: PaperBrokerSettings) -> None:
    sig = {"signal_class": "kern", "direction": "long"}
    q = qty_with_stop_budget(
        settings, sig, "kern", context={"account_equity": "10000"}
    )
    assert q == Decimal(str(settings.strat_base_qty_btc))
