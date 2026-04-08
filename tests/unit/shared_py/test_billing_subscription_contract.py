"""Tests fuer shared_py.billing_subscription_contract (Prompt 8)."""

from __future__ import annotations

from shared_py.billing_subscription_contract import (
    DEFAULT_PROFIT_SHARE_BASIS_POINTS,
    STANDARD_DAILY_NET_CENTS_EUR,
    STANDARD_SUBSCRIPTION_PLAN_TEMPLATES,
    billing_subscription_descriptor,
    contract_accepted_for_billing,
    plan_template_by_code,
    profit_share_fee_cents_default,
    requires_contract_acceptance_to_proceed_to_paid_live,
    subscription_list_gross_preview_de,
)
from shared_py.customer_lifecycle import LifecyclePhase


def test_daily_net_is_10_eur() -> None:
    assert STANDARD_DAILY_NET_CENTS_EUR == 1000


def test_profit_share_default_10_percent() -> None:
    assert DEFAULT_PROFIT_SHARE_BASIS_POINTS == 1000
    assert profit_share_fee_cents_default(100_000) == 10_000


def test_four_standard_plans() -> None:
    assert len(STANDARD_SUBSCRIPTION_PLAN_TEMPLATES) == 4


def test_plan_template_by_code() -> None:
    p = plan_template_by_code("sub_daily_std")
    assert p is not None
    assert p.net_cents_per_period == STANDARD_DAILY_NET_CENTS_EUR


def test_gross_preview_daily_has_19_vat() -> None:
    rows = subscription_list_gross_preview_de()
    daily = next(r for r in rows if r["code"] == "sub_daily_std")
    assert daily["net_cents"] == 1000
    assert daily["vat_cents"] == 190
    assert daily["gross_cents"] == 1190


def test_contract_required_after_trial_ended() -> None:
    assert requires_contract_acceptance_to_proceed_to_paid_live(LifecyclePhase.TRIAL_ENDED) is True
    assert requires_contract_acceptance_to_proceed_to_paid_live(LifecyclePhase.CONTRACT_PENDING) is True


def test_no_contract_required_during_trial() -> None:
    assert requires_contract_acceptance_to_proceed_to_paid_live(LifecyclePhase.TRIAL_ACTIVE) is False


def test_contract_accepted_phases() -> None:
    assert contract_accepted_for_billing(LifecyclePhase.CONTRACT_ACTIVE) is True
    assert contract_accepted_for_billing(LifecyclePhase.LIVE_RELEASED) is True


def test_requires_contract_false_when_contract_active() -> None:
    assert requires_contract_acceptance_to_proceed_to_paid_live(LifecyclePhase.CONTRACT_ACTIVE) is False


def test_descriptor() -> None:
    d = billing_subscription_descriptor()
    assert d["standard_plan_count"] == 4
    assert d["prompt13_db_migration"] == "609_subscription_billing_ledger"
    assert d["standard_vat_rate_percent"] == 19


def test_gross_preview_year_matches_prompt13_formula() -> None:
    rows = subscription_list_gross_preview_de()
    y = next(r for r in rows if r["code"] == "sub_year_std")
    assert y["net_cents"] == 365_000
    assert y["vat_cents"] == 69_350
    assert y["gross_cents"] == 434_350
