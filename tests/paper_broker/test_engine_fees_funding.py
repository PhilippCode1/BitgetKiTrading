from __future__ import annotations

from decimal import Decimal

from paper_broker.engine.fees import calc_transaction_fee_usdt, order_notional_usdt
from paper_broker.engine.funding import calc_funding_usdt
from paper_broker.engine.liquidation import (
    realized_pnl_liquidation_fill,
    should_liquidate_approx,
)
from paper_broker.engine.slippage import (
    apply_slippage_bps,
    volatility_effective_slippage_bps,
    walk_asks_fill,
    worst_price_buy_liquidation_top_asks,
    worst_price_sell_liquidation_top_bids,
)


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


def test_liquidation_stress_worse_pnl_long_than_mid() -> None:
    """Cascades: 5. Bid unter dem Mid -> groesserer realisierter Verlust (Long)."""
    qty = Decimal("1")
    entry = Decimal("50000")
    mark = Decimal("45000")
    pnl_at_mark = realized_pnl_liquidation_fill("long", qty, entry, mark)
    bids: list[tuple[Decimal, Decimal]] = [
        (Decimal("44900"), Decimal("0.1")),
        (Decimal("44850"), Decimal("0.1")),
        (Decimal("44800"), Decimal("0.1")),
        (Decimal("44700"), Decimal("0.1")),
        (Decimal("42000"), Decimal("5.0")),
    ]
    w = worst_price_sell_liquidation_top_bids(bids, 5)
    assert w is not None
    pnl_stress = realized_pnl_liquidation_fill("long", qty, entry, w)
    assert pnl_stress < pnl_at_mark, (pnl_stress, pnl_at_mark)


def test_liquidation_high_atr_sells_deeper_loss_than_seitwaerts() -> None:
    """
    ATR-Proxy erhoeht effektive Slippage; bei identischem Mid hat Long eine schlechtere
    Ersatz-Fill-Approximation (hoehere sell-Bps) als in Seitwaerts-Phase.
    """
    base = Decimal("3")
    low_vol = {"atrp_14": Decimal("0.02")}  # 2% Skala, moderat
    high_vol = {"atrp_14": Decimal("0.35"), "vpin_0_1": Decimal("0.4")}

    bps_calm = volatility_effective_slippage_bps(
        base,
        tick_payload=low_vol,
        bps_per_atr_0_1=Decimal("2"),
        bps_per_vpin_0_1=Decimal("2"),
    )
    bps_storm = volatility_effective_slippage_bps(
        base,
        tick_payload=high_vol,
        bps_per_atr_0_1=Decimal("2"),
        bps_per_vpin_0_1=Decimal("2"),
    )
    assert bps_storm > bps_calm
    mid = Decimal("100")
    sell_c = apply_slippage_bps(mid, bps_calm, "sell")
    sell_s = apply_slippage_bps(mid, bps_storm, "sell")
    pnl_c = (sell_c - Decimal("105")) * Decimal(1)  # entry 105 long exit sell
    pnl_s = (sell_s - Decimal("105")) * Decimal(1)
    assert pnl_s < pnl_c


def test_liquidation_short_asks_worst() -> None:
    asks: list[tuple[Decimal, Decimal]] = [
        (Decimal("45010"), Decimal("0.1")),
        (Decimal("45050"), Decimal("0.1")),
        (Decimal("45100"), Decimal("0.1")),
        (Decimal("46000"), Decimal("2")),
    ]
    w = worst_price_buy_liquidation_top_asks(asks, 3)
    assert w == Decimal("45100")
