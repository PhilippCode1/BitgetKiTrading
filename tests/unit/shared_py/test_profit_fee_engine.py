"""High-Water-Mark Gewinnbeteiligung (Prompt 15)."""

from __future__ import annotations

import pytest

from shared_py.profit_fee_engine import compute_profit_fee_statement_numbers


def test_incremental_above_hwm_10_percent() -> None:
    out = compute_profit_fee_statement_numbers(
        cumulative_realized_pnl_cents=110_000,
        high_water_mark_before_cents=100_000,
        fee_rate_basis_points=1000,
    )
    assert out["incremental_profit_cents"] == 10_000
    assert out["fee_amount_cents"] == 1_000
    assert out["high_water_mark_after_approval_cents"] == 110_000


def test_no_fee_when_below_hwm() -> None:
    out = compute_profit_fee_statement_numbers(
        cumulative_realized_pnl_cents=80_000,
        high_water_mark_before_cents=100_000,
        fee_rate_basis_points=1000,
    )
    assert out["incremental_profit_cents"] == 0
    assert out["fee_amount_cents"] == 0
    assert out["high_water_mark_after_approval_cents"] == 100_000


def test_negative_cumulative_no_incremental_until_hwm_exceeded() -> None:
    out = compute_profit_fee_statement_numbers(
        cumulative_realized_pnl_cents=-20_000,
        high_water_mark_before_cents=50_000,
        fee_rate_basis_points=1000,
    )
    assert out["incremental_profit_cents"] == 0
    assert out["fee_amount_cents"] == 0


def test_hwm_after_max_of_peak_and_cumulative() -> None:
    out = compute_profit_fee_statement_numbers(
        cumulative_realized_pnl_cents=90_000,
        high_water_mark_before_cents=100_000,
        fee_rate_basis_points=1000,
    )
    assert out["high_water_mark_after_approval_cents"] == 100_000


def test_invalid_rate_rejected() -> None:
    with pytest.raises(ValueError):
        compute_profit_fee_statement_numbers(
            cumulative_realized_pnl_cents=1,
            high_water_mark_before_cents=0,
            fee_rate_basis_points=10_001,
        )
