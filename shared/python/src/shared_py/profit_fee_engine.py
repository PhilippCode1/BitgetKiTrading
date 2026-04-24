"""
Gewinnbeteiligung mit High-Water-Mark (HWM) auf **Equity-Basis** (Migration 611 / Prompt 43).

Alle Geldbetraege in **USD-Cent** (Ganzzahl). Gebuehr: ``profit_share_fee_cents`` aus
``commercial_data_model`` (Basispunkte, 2000 = 20 %, 1000 = 10 %).

Semantik
--------
- **current_equity_value_cents**: aktueller Konten-/Performance-Stand am Periodenende, der
  vertraglich der Gebuehrenbemessung dient (kumulativer realisierter PnL bzw. Equity, je
  nach Import).
- **highest_equity_value_cents (HWM)**: bisheriger Hoechststand: Es wird nur der Betrag
  oberhalb dieses Niveaus belastet (keine Doppelgebuehr; Verlustphasen: solange
  ``current < HWM``, kein neuer ``net_profit``).
- Externe **Ein-/Auszahlungen** verschieben weder den tradingbedingten Fortschritt noch
  sollen sie als kuenstliche Gewinne zaehlen: dazu HWM in der DB um den gleichen Centbetrag
  mitziehen (siehe ``db_profit_fee.apply_hwm_external_cashflow_list_usd``).
"""

from __future__ import annotations

from typing import Any, Literal

from shared_py.commercial_data_model import profit_share_fee_cents

PROFIT_FEE_ENGINE_VERSION = "profit-fee-engine-2-hwm-equity"

TradingMode = Literal["paper", "live"]


def compute_profit_fee_hwm_statement(
    *,
    current_equity_value_cents: int,
    highest_equity_value_before_cents: int,
    fee_rate_basis_points: int,
) -> dict[str, Any]:
    """
    Berechnet **net_profit** oberhalb HWM und die Profifee.

    - ``net_profit = max(0, current_equity - HWM)``
    - Nur bei ``net_profit > 0`` faellt ``fee_amount_cents > 0`` (anteilig nach Satz).
    - Nach freigegebener Abrechnung: neuer HWM = max(vorheriger HWM, aktuelle Equity);
      bleibt der Kunde unter dem alten HWM (Drawdown), wird der HWM **nicht** nach unten
      versetzt (klassisches HWM).
    """
    if highest_equity_value_before_cents < 0:
        raise ValueError("highest_equity_value_before_cents must be non-negative")
    if fee_rate_basis_points < 0 or fee_rate_basis_points > 10000:
        raise ValueError("fee_rate_basis_points out of range 0..10000")

    net_profit = max(0, current_equity_value_cents - highest_equity_value_before_cents)
    fee = profit_share_fee_cents(net_profit, fee_rate_basis_points)
    hwm_after = max(highest_equity_value_before_cents, current_equity_value_cents)

    return {
        "schema_version": PROFIT_FEE_ENGINE_VERSION,
        "current_equity_value_cents": current_equity_value_cents,
        "highest_equity_value_before_cents": highest_equity_value_before_cents,
        "net_profit_cents": net_profit,
        "fee_rate_basis_points": fee_rate_basis_points,
        "fee_amount_cents": fee,
        "highest_equity_value_after_approval_cents": hwm_after,
        # Legacy-Feldnamen (DB / API)
        "cumulative_realized_pnl_cents": current_equity_value_cents,
        "high_water_mark_before_cents": highest_equity_value_before_cents,
        "incremental_profit_cents": net_profit,
        "high_water_mark_after_approval_cents": hwm_after,
    }


def compute_profit_fee_statement_numbers(
    *,
    cumulative_realized_pnl_cents: int,
    high_water_mark_before_cents: int,
    fee_rate_basis_points: int,
) -> dict[str, Any]:
    """
    Abwaertskompatibler Einstieg: ``cumulative_realized_pnl_cents`` = Equity-Messwert
    (historischer Parametername), ``high_water_mark_before_cents`` = HWM.
    """
    return compute_profit_fee_hwm_statement(
        current_equity_value_cents=cumulative_realized_pnl_cents,
        highest_equity_value_before_cents=high_water_mark_before_cents,
        fee_rate_basis_points=fee_rate_basis_points,
    )


def profit_fee_engine_descriptor() -> dict[str, str]:
    return {"profit_fee_engine_version": PROFIT_FEE_ENGINE_VERSION}
