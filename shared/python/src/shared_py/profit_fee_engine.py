"""
Gewinnbeteiligung mit High-Water-Mark auf kumulativem realisierten PnL (Prompt 15).

Alle Geldbetraege in **USD-Cent** (Ganzzahl). Gebuehr: ``profit_share_fee_cents`` aus
``commercial_data_model`` (Basispunkte, 1000 = 10 %).
"""

from __future__ import annotations

from typing import Any, Literal

from shared_py.commercial_data_model import profit_share_fee_cents

PROFIT_FEE_ENGINE_VERSION = "profit-fee-engine-1"

TradingMode = Literal["paper", "live"]


def compute_profit_fee_statement_numbers(
    *,
    cumulative_realized_pnl_cents: int,
    high_water_mark_before_cents: int,
    fee_rate_basis_points: int,
) -> dict[str, Any]:
    """
    Berechnet inkrementelle Gewinnbasis und Gebuehr.

    HWM-Logik: Es wird nur der Betrag oberhalb des bisherigen Hoechststands der
    kumulativen realisierten PnL-Zeitreihe belastet (keine Doppelgebuehr bei
    erneutem Erreichen eines alten Peaks).
    """
    # Kumulativer realisierter PnL darf negativ sein (Nettoverlust seit Start).
    if high_water_mark_before_cents < 0:
        raise ValueError("high_water_mark_before_cents must be non-negative")
    if fee_rate_basis_points < 0 or fee_rate_basis_points > 10000:
        raise ValueError("fee_rate_basis_points out of range 0..10000")

    incremental = max(0, cumulative_realized_pnl_cents - high_water_mark_before_cents)
    fee = profit_share_fee_cents(incremental, fee_rate_basis_points)
    hwm_after = max(high_water_mark_before_cents, cumulative_realized_pnl_cents)

    return {
        "schema_version": PROFIT_FEE_ENGINE_VERSION,
        "cumulative_realized_pnl_cents": cumulative_realized_pnl_cents,
        "high_water_mark_before_cents": high_water_mark_before_cents,
        "incremental_profit_cents": incremental,
        "fee_rate_basis_points": fee_rate_basis_points,
        "fee_amount_cents": fee,
        "high_water_mark_after_approval_cents": hwm_after,
    }


def profit_fee_engine_descriptor() -> dict[str, str]:
    return {"profit_fee_engine_version": PROFIT_FEE_ENGINE_VERSION}
