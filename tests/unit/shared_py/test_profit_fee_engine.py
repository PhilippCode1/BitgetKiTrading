"""High-Water-Mark Gewinnbeteiligung (Prompt 15)."""

from __future__ import annotations

import pytest

from shared_py.profit_fee_engine import (
    compute_profit_fee_hwm_statement,
    compute_profit_fee_statement_numbers,
)


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


def test_hwm_loss_offset_three_phases_drawdown_partial_recovery() -> None:
    """
    +1000 Gewinn (20 % Fee), -500 (keine Fee), +300 Erholung: unter erster HWM -> keine weitere Fee.
    Betraege in USDT = USD-Cent (z. B. 1000 USDT = 100_000 cent).
    """
    rate = 2000
    hwm = 0
    p1 = compute_profit_fee_hwm_statement(
        current_equity_value_cents=100_000,
        highest_equity_value_before_cents=hwm,
        fee_rate_basis_points=rate,
    )
    assert p1["net_profit_cents"] == 100_000
    assert p1["fee_amount_cents"] == 20_000
    hwm = p1["highest_equity_value_after_approval_cents"]
    p2 = compute_profit_fee_hwm_statement(
        current_equity_value_cents=50_000,
        highest_equity_value_before_cents=hwm,
        fee_rate_basis_points=rate,
    )
    assert p2["fee_amount_cents"] == 0
    assert p2["highest_equity_value_after_approval_cents"] == 100_000
    hwm = p2["highest_equity_value_after_approval_cents"]
    p3 = compute_profit_fee_hwm_statement(
        current_equity_value_cents=80_000,
        highest_equity_value_before_cents=hwm,
        fee_rate_basis_points=rate,
    )
    assert p3["fee_amount_cents"] == 0
    assert p3["net_profit_cents"] == 0
    assert p3["highest_equity_value_after_approval_cents"] == 100_000


def test_cashflow_aligned_hwm_prevents_deposit_masquerading_as_profit() -> None:
    """
    HWM mit Einzahlung um +1000 USD (Cent) nach oben: Equity nur Cash -> keine Fee-Basis.
    (Entspricht apply_hwm_external_cashflow vor Periodenvergleich.)
    """
    hwm = 100_000
    p = compute_profit_fee_hwm_statement(
        current_equity_value_cents=100_000,
        highest_equity_value_before_cents=hwm,
        fee_rate_basis_points=2000,
    )
    assert p["net_profit_cents"] == 0
    assert p["fee_amount_cents"] == 0
