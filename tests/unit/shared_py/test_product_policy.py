"""Tests fuer shared_py.product_policy (Prompt 1 / Produktbrief)."""

from __future__ import annotations

from shared_py.product_policy import (
    TRIAL_PERIOD_DAYS,
    CommercialExecutionMode,
    CustomerCommercialGates,
    demo_trading_allowed,
    exchange_api_connection_allowed,
    live_trading_allowed,
    order_placement_permissions,
    organization_display_name,
    product_policy_descriptor,
    resolve_execution_mode,
    super_admin_display_name,
    telegram_live_actions_allowed,
    trial_period_days,
)


def test_fixed_constants() -> None:
    assert TRIAL_PERIOD_DAYS == 21
    assert trial_period_days() == 21
    assert "Modul Mate" in organization_display_name()
    assert super_admin_display_name() == "Philipp Crljic"


def test_live_requires_contract_admin_subscription_when_flag_on() -> None:
    gates = CustomerCommercialGates(
        trial_active=False,
        contract_accepted=True,
        admin_live_trading_granted=True,
        subscription_active=False,
    )
    assert resolve_execution_mode(gates) == CommercialExecutionMode.DEMO
    assert not live_trading_allowed(gates)


def test_live_ok_when_subscription_active() -> None:
    gates = CustomerCommercialGates(
        trial_active=False,
        contract_accepted=True,
        admin_live_trading_granted=True,
        subscription_active=True,
    )
    assert resolve_execution_mode(gates) == CommercialExecutionMode.LIVE
    assert live_trading_allowed(gates)
    assert telegram_live_actions_allowed(gates)


def test_trial_demo_without_contract() -> None:
    gates = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=False,
        admin_live_trading_granted=False,
        subscription_active=False,
    )
    assert resolve_execution_mode(gates) == CommercialExecutionMode.DEMO
    assert demo_trading_allowed(gates)
    assert not live_trading_allowed(gates)


def test_suspended_blocks_all_execution() -> None:
    gates = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=True,
        admin_live_trading_granted=True,
        subscription_active=True,
        account_suspended=True,
    )
    assert resolve_execution_mode(gates) == CommercialExecutionMode.NONE
    assert not demo_trading_allowed(gates)
    assert not live_trading_allowed(gates)


def test_paused_blocks_execution() -> None:
    gates = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=False,
        admin_live_trading_granted=False,
        subscription_active=False,
        account_paused=True,
    )
    assert resolve_execution_mode(gates) == CommercialExecutionMode.NONE


def test_exchange_api_live_execution_gate() -> None:
    ok_gates = CustomerCommercialGates(
        trial_active=False,
        contract_accepted=True,
        admin_live_trading_granted=True,
        subscription_active=True,
    )
    allowed, code = exchange_api_connection_allowed(ok_gates, purpose="live_execution")
    assert allowed and code == "ok"

    bad = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=False,
        admin_live_trading_granted=False,
        subscription_active=False,
    )
    allowed2, code2 = exchange_api_connection_allowed(bad, purpose="live_execution")
    assert not allowed2 and code2 == "live_trading_not_permitted"


def test_product_policy_descriptor_keys() -> None:
    d = product_policy_descriptor()
    assert d["trial_period_days"] == 21
    assert "product_policy_module_version" in d


def test_order_placement_permissions_splits_demo_vs_live() -> None:
    live_gates = CustomerCommercialGates(
        trial_active=False,
        contract_accepted=True,
        admin_live_trading_granted=True,
        subscription_active=True,
    )
    lp = order_placement_permissions(live_gates)
    assert lp.commercial_execution_mode == CommercialExecutionMode.LIVE
    assert lp.can_place_live_orders is True
    assert lp.can_place_demo_orders is False

    demo_gates = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=False,
        admin_live_trading_granted=False,
        subscription_active=False,
    )
    dp = order_placement_permissions(demo_gates)
    assert dp.commercial_execution_mode == CommercialExecutionMode.DEMO
    assert dp.can_place_demo_orders is True
    assert dp.can_place_live_orders is False
