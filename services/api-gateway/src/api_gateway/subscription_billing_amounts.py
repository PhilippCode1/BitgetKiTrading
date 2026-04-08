"""Rechnungspositionen aus Katalogzeilen (Gateway, Prompt 13)."""

from __future__ import annotations

from typing import Any

from shared_py.subscription_billing_pricing import amounts_from_net_cents_and_vat_bps


def plan_row_to_line_amounts(
    plan: dict[str, Any],
    *,
    period_label: str | None = None,
) -> dict[str, Any]:
    net = int(plan["net_amount_cents"])
    bps = int(plan["vat_rate_bps"])
    a = amounts_from_net_cents_and_vat_bps(net, bps)
    desc = f"Abo {plan['display_name_de']} ({plan['billing_interval']})"
    if period_label:
        desc = f"{desc} — {period_label}"
    return {
        "description": desc,
        "net_cents": a["net_cents"],
        "vat_cents": a["vat_cents"],
        "gross_cents": a["gross_cents"],
    }


def plan_row_to_public_amounts(plan: dict[str, Any]) -> dict[str, int | str]:
    """Fuer API: Netto/USt/Brutto zur Anzeige."""
    net = int(plan["net_amount_cents"])
    bps = int(plan["vat_rate_bps"])
    a = amounts_from_net_cents_and_vat_bps(net, bps)
    return {
        "plan_code": str(plan["plan_code"]),
        "billing_interval": str(plan["billing_interval"]),
        "display_name_de": str(plan["display_name_de"]),
        "currency": str(plan["currency"]),
        "vat_rate_bps": bps,
        "net_cents": a["net_cents"],
        "vat_cents": a["vat_cents"],
        "gross_cents": a["gross_cents"],
    }
