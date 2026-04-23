from __future__ import annotations

import random
from decimal import Decimal

import pytest

from live_broker.orders.passive_order_manager import (
    chase_price_within_slippage,
    orderflow_wall_against_side,
    passive_limit_price,
    passive_maker_trace_enabled,
    plan_iceberg_sizes,
)


def test_passive_maker_trace_enabled_dict_explicit() -> None:
    assert passive_maker_trace_enabled(settings_default=False, trace={"predatory_passive_maker": {"enabled": True}})
    assert not passive_maker_trace_enabled(
        settings_default=True, trace={"predatory_passive_maker": {"enabled": False}}
    )


def test_passive_limit_price() -> None:
    bid = Decimal("100")
    ask = Decimal("101")
    assert passive_limit_price(side="buy", bid=bid, ask=ask) == bid
    assert passive_limit_price(side="sell", bid=bid, ask=ask) == ask


def test_iceberg_sizes_sum_and_randomization_window() -> None:
    rng = random.Random(42)
    total = Decimal("10")
    sizes = plan_iceberg_sizes(total, 5, rng)
    assert len(sizes) == 5
    assert sum(sizes) == total
    assert all(s > 0 for s in sizes)
    rng2 = random.Random(99)
    other = plan_iceberg_sizes(total, 5, rng2)
    assert sum(other) == total
    assert other != sizes


def test_chase_slippage_budget() -> None:
    anchor = Decimal("100")
    assert chase_price_within_slippage(
        anchor_price=anchor,
        new_limit_price=Decimal("100.2"),
        max_slippage_bps=25.0,
    )
    assert not chase_price_within_slippage(
        anchor_price=anchor,
        new_limit_price=Decimal("101"),
        max_slippage_bps=25.0,
    )


@pytest.mark.parametrize(
    ("side", "imb", "thr", "expect_wall"),
    [
        ("buy", -0.8, 0.55, True),
        ("buy", 0.1, 0.55, False),
        ("sell", 0.8, 0.55, True),
        ("sell", -0.1, 0.55, False),
    ],
)
def test_orderflow_wall(side: str, imb: float, thr: float, expect_wall: bool) -> None:
    assert orderflow_wall_against_side(side=side, orderflow_imbalance=imb, threshold=thr) == expect_wall
