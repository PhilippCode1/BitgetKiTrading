from __future__ import annotations

from decimal import Decimal

from paper_broker.engine.fees import calc_transaction_fee_usdt, order_notional_usdt
from paper_broker.engine.funding import calc_funding_usdt
from paper_broker.engine.liquidation import should_liquidate_approx
from paper_broker.engine.slippage import apply_slippage_bps, walk_asks_fill


def test_fee_bitget_formula() -> None:
    fee = calc_transaction_fee_usdt(
        Decimal("0.05"), Decimal("60000"), Decimal("0.0006")
    )
    assert fee == Decimal("0.05") * Decimal("60000") * Decimal("0.0006")
    assert order_notional_usdt(Decimal("1"), Decimal("2")) == Decimal("2")


def test_funding_direction_positive_rate() -> None:
    v = Decimal("1000")
    r = Decimal("0.0001")
    assert calc_funding_usdt(v, r, "long") < 0
    assert calc_funding_usdt(v, r, "short") > 0


def test_funding_direction_negative_rate() -> None:
    v = Decimal("1000")
    r = Decimal("-0.0001")
    assert calc_funding_usdt(v, r, "long") > 0
    assert calc_funding_usdt(v, r, "short") < 0


def test_slippage_walk_asks() -> None:
    asks = [(Decimal("100"), Decimal("1")), (Decimal("101"), Decimal("2"))]
    avg, filled, ok = walk_asks_fill(asks, Decimal("2"))
    assert ok
    assert filled == Decimal("2")
    assert avg == (Decimal("100") + Decimal("101")) / Decimal("2")


def test_slippage_bps() -> None:
    mid = Decimal("60000")
    buy = apply_slippage_bps(mid, Decimal("10"), "buy")
    assert buy > mid


def test_liquidation_approx_triggers() -> None:
    assert should_liquidate_approx(
        isolated_margin=Decimal("100"),
        qty=Decimal("1"),
        entry_avg=Decimal("50000"),
        mark=Decimal("40000"),
        side="long",
        accrued_fees=Decimal("5"),
        net_funding_ledger=Decimal("0"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
    )
