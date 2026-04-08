"""Prompt 13: USt aus bps und Summen-Validierung."""

from __future__ import annotations

import pytest

from shared_py.subscription_billing_pricing import (
    amounts_from_net_cents_and_vat_bps,
    subscription_billing_pricing_descriptor,
    validate_invoice_lines_match_totals,
    vat_rate_decimal_from_bps,
)


def test_vat_bps_19_percent_matches_standard_plans() -> None:
    assert amounts_from_net_cents_and_vat_bps(1000, 1900) == {
        "net_cents": 1000,
        "vat_cents": 190,
        "gross_cents": 1190,
    }
    assert amounts_from_net_cents_and_vat_bps(7000, 1900) == {
        "net_cents": 7000,
        "vat_cents": 1330,
        "gross_cents": 8330,
    }
    assert amounts_from_net_cents_and_vat_bps(30000, 1900) == {
        "net_cents": 30000,
        "vat_cents": 5700,
        "gross_cents": 35700,
    }
    assert amounts_from_net_cents_and_vat_bps(365000, 1900) == {
        "net_cents": 365000,
        "vat_cents": 69350,
        "gross_cents": 434350,
    }


def test_validate_lines_ok() -> None:
    validate_invoice_lines_match_totals(
        [
            {"net_cents": 100, "vat_cents": 19, "gross_cents": 119},
            {"net_cents": 50, "vat_cents": 10, "gross_cents": 60},
        ],
        total_net_cents=150,
        total_vat_cents=29,
        total_gross_cents=179,
    )


def test_validate_lines_mismatch() -> None:
    with pytest.raises(ValueError, match="invoice_line_totals_mismatch"):
        validate_invoice_lines_match_totals(
            [{"net_cents": 100, "vat_cents": 19, "gross_cents": 119}],
            total_net_cents=100,
            total_vat_cents=20,
            total_gross_cents=119,
        )


def test_vat_rate_decimal_from_bps_bounds() -> None:
    with pytest.raises(ValueError):
        vat_rate_decimal_from_bps(-1)
    with pytest.raises(ValueError):
        vat_rate_decimal_from_bps(10001)


def test_descriptor() -> None:
    d = subscription_billing_pricing_descriptor()
    assert d["default_vat_rate_bps"] == 1900
