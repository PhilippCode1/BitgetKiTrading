from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from shared_py.bitget.execution_guards import (
    market_spread_slippage_cap_reasons,
    preset_stop_distance_floor_reasons,
    preset_stop_vs_spread_reasons,
    reduce_only_position_consistency_reasons,
    replace_size_safety_reasons,
)


def test_spread_cap_blocks_wide_book() -> None:
    bid = Decimal("100")
    ask = Decimal("104")
    reasons = market_spread_slippage_cap_reasons(
        side="buy",
        bid=bid,
        ask=ask,
        max_spread_half_bps=Decimal("100"),
    )
    assert reasons and "execution_guard_spread_half_bps_exceeds_cap" in reasons[0]


def test_stop_distance_floor() -> None:
    r = preset_stop_distance_floor_reasons(
        stop_price=Decimal("99.9"),
        reference_price=Decimal("100"),
        min_distance_bps=Decimal("50"),
    )
    assert r and "below_floor" in r[0]


def test_stop_vs_spread_mult() -> None:
    r = preset_stop_vs_spread_reasons(
        stop_price=Decimal("99.99"),
        reference_price=Decimal("100"),
        bid=Decimal("99.9"),
        ask=Decimal("100.1"),
        min_stop_to_spread_mult=Decimal("10"),
    )
    assert r and "too_close_to_spread" in r[0]


def test_reduce_only_mismatch() -> None:
    r = reduce_only_position_consistency_reasons(
        reduce_only=True,
        order_side="buy",
        position_net_base=Decimal("1"),
        require_known_position=True,
    )
    assert r == ["execution_guard_reduce_only_side_mismatch_long"]


def test_replace_blocks_size_up_on_reduce_only() -> None:
    r = replace_size_safety_reasons(
        existing_reduce_only=True,
        old_size=Decimal("1"),
        new_size=Decimal("1.1"),
    )
    assert r == ["execution_guard_replace_increase_size_blocked_reduce_only"]
