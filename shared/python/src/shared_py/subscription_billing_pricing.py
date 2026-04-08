"""
Zentrale Abo-Preislogik (Prompt 13) — Netto/USt/Brutto aus Katalogzeilen.

USt wird aus Basispunkten (bps) auf Netto-Cent berechnet, konsistent mit
`commercial_data_model.vat_amounts_from_net_cents`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared_py.commercial_data_model import vat_amounts_from_net_cents

SUBSCRIPTION_BILLING_PRICING_MODULE_VERSION = "1.0.0"


def vat_rate_decimal_from_bps(vat_rate_bps: int) -> Decimal:
    if vat_rate_bps < 0 or vat_rate_bps > 10_000:
        raise ValueError("vat_rate_bps out of range")
    return Decimal(vat_rate_bps) / Decimal(10000)


def amounts_from_net_cents_and_vat_bps(net_cents: int, vat_rate_bps: int) -> dict[str, int]:
    """Netto-Cent + USt in bps -> net/vat/gross Cent (ganzzahlig, Halbauf)."""
    rate = vat_rate_decimal_from_bps(vat_rate_bps)
    return vat_amounts_from_net_cents(net_cents, rate)


def validate_invoice_lines_match_totals(
    lines: list[dict[str, Any]],
    *,
    total_net_cents: int,
    total_vat_cents: int,
    total_gross_cents: int,
) -> None:
    """Prueft Summe der Positionen gegen Rechnungskopf."""
    sn = sv = sg = 0
    for row in lines:
        sn += int(row["net_cents"])
        sv += int(row["vat_cents"])
        sg += int(row["gross_cents"])
    if (sn, sv, sg) != (total_net_cents, total_vat_cents, total_gross_cents):
        raise ValueError("invoice_line_totals_mismatch")


def subscription_billing_pricing_descriptor() -> dict[str, str | int]:
    return {
        "subscription_billing_pricing_module_version": SUBSCRIPTION_BILLING_PRICING_MODULE_VERSION,
        "default_vat_rate_bps": 1900,
        "reference_daily_net_cents_eur": 1000,
    }
