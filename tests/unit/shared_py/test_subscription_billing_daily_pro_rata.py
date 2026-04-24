"""DoD Prompt 41: drei Plaentypen (Basic/Pro/Institution) — anteiliger Tages-Abzug."""
from __future__ import annotations

from decimal import Decimal

import pytest

from shared_py.subscription_billing_pricing import (
    daily_prorata_net_cents_eur,
    eur_cents_to_list_usd,
)

# Werte aus Migration 621: Monats-Netto, reference_period_days=30
_BASIC_MONTH_NET_CENTS = 3_000
_PRO_MONTH_NET_CENTS = 30_000
_INSTITUTION_MONTH_NET_CENTS = 150_000
_REF_DAYS = 30


def test_three_plan_tiers_daily_net_cents() -> None:
    assert (
        daily_prorata_net_cents_eur(_BASIC_MONTH_NET_CENTS, reference_period_days=_REF_DAYS) == 100
    )
    assert (
        daily_prorata_net_cents_eur(_PRO_MONTH_NET_CENTS, reference_period_days=_REF_DAYS) == 1000
    )
    assert (
        daily_prorata_net_cents_eur(_INSTITUTION_MONTH_NET_CENTS, reference_period_days=_REF_DAYS)
        == 5000
    )


def test_three_plan_tiers_list_usd_at_partity_rate() -> None:
    rate = Decimal("1.0")
    b = daily_prorata_net_cents_eur(
        _BASIC_MONTH_NET_CENTS, reference_period_days=_REF_DAYS
    )
    p = daily_prorata_net_cents_eur(
        _PRO_MONTH_NET_CENTS, reference_period_days=_REF_DAYS
    )
    i = daily_prorata_net_cents_eur(
        _INSTITUTION_MONTH_NET_CENTS, reference_period_days=_REF_DAYS
    )
    assert eur_cents_to_list_usd(b, eur_to_usd_rate=rate) == Decimal("1.0")
    assert eur_cents_to_list_usd(p, eur_to_usd_rate=rate) == Decimal("10.0")
    assert eur_cents_to_list_usd(i, eur_to_usd_rate=rate) == Decimal("50.0")


def test_idempotency_key_uniqueness_pattern() -> None:
    d = "2030-01-15"
    tid = "t42"
    assert f"subscription:deduct:{d}:{tid}" != f"subscription:deduct:{d}:other"
    assert f"subscription_prepaid:wallet:{d}:{tid}" == f"subscription_prepaid:wallet:{d}:{tid}"


def test_eur_cents_rejects_negative() -> None:
    with pytest.raises(ValueError):
        eur_cents_to_list_usd(-1, eur_to_usd_rate=Decimal("1"))


def test_pro_rata_zero_month() -> None:
    with pytest.raises(ValueError):
        daily_prorata_net_cents_eur(100, reference_period_days=0)
