"""Tests fuer shared_py.customer_lifecycle (Prompt 2)."""

from __future__ import annotations

from shared_py.customer_lifecycle import (
    ALLOWED_LIFECYCLE_TRANSITIONS,
    CustomerLifecycleSnapshot,
    LifecyclePhase,
    PlatformRole,
    TransitionActor,
    allowed_lifecycle_targets,
    commercial_gates_from_lifecycle,
    customer_journey_title_de,
    customer_lifecycle_descriptor,
    derive_customer_capabilities,
    is_lifecycle_transition_allowed,
    platform_role_is_full_admin,
)
from shared_py.product_policy import live_trading_allowed


def test_transition_admin_live_gate() -> None:
    assert is_lifecycle_transition_allowed(
        LifecyclePhase.LIVE_PREPARED,
        LifecyclePhase.LIVE_RELEASED,
        TransitionActor.ADMIN,
    )
    assert not is_lifecycle_transition_allowed(
        LifecyclePhase.LIVE_PREPARED,
        LifecyclePhase.LIVE_RELEASED,
        TransitionActor.USER,
    )


def test_transition_same_phase_always_ok() -> None:
    assert is_lifecycle_transition_allowed(
        LifecyclePhase.TRIAL_ACTIVE,
        LifecyclePhase.TRIAL_ACTIVE,
        TransitionActor.USER,
    )


def test_admin_revoke_live() -> None:
    assert is_lifecycle_transition_allowed(
        LifecyclePhase.LIVE_RELEASED,
        LifecyclePhase.LIVE_PREPARED,
        TransitionActor.ADMIN,
    )


def test_trial_to_contract_early_user() -> None:
    assert is_lifecycle_transition_allowed(
        LifecyclePhase.TRIAL_ACTIVE,
        LifecyclePhase.CONTRACT_PENDING,
        TransitionActor.USER,
    )


def test_allowed_targets_admin_from_prepared() -> None:
    t = allowed_lifecycle_targets(LifecyclePhase.LIVE_PREPARED, TransitionActor.ADMIN)
    assert LifecyclePhase.LIVE_RELEASED in t
    assert LifecyclePhase.LIVE_PREPARED in t


def test_commercial_gates_live_released() -> None:
    snap = CustomerLifecycleSnapshot(phase=LifecyclePhase.LIVE_RELEASED)
    g = commercial_gates_from_lifecycle(snap)
    assert g.contract_accepted and g.subscription_active and g.admin_live_trading_granted
    assert live_trading_allowed(g)


def test_commercial_gates_trial_only_demo_path() -> None:
    snap = CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ACTIVE)
    g = commercial_gates_from_lifecycle(snap)
    assert g.trial_active
    assert not g.contract_accepted
    assert not live_trading_allowed(g)


def test_capabilities_trial_demo_not_live() -> None:
    cap = derive_customer_capabilities(CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ACTIVE))
    assert cap.demo_trading
    assert not cap.execute_live_orders
    assert cap.start_trial is False
    assert cap.verify_email is False


def test_capabilities_email_verified_can_start_trial() -> None:
    cap = derive_customer_capabilities(CustomerLifecycleSnapshot(phase=LifecyclePhase.EMAIL_VERIFIED))
    assert cap.start_trial
    assert not cap.demo_trading


def test_capabilities_suspended_blocks_demo() -> None:
    cap = derive_customer_capabilities(
        CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ACTIVE, is_suspended=True)
    )
    assert not cap.demo_trading
    assert not cap.telegram_info_messages


def test_capabilities_no_store_creds_before_contract() -> None:
    cap = derive_customer_capabilities(CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ACTIVE))
    assert not cap.store_live_exchange_credentials


def test_journey_titles_german() -> None:
    assert "Testkunde" in customer_journey_title_de(LifecyclePhase.TRIAL_ACTIVE)
    assert "Echtgeld" in customer_journey_title_de(LifecyclePhase.LIVE_RELEASED)


def test_platform_admin() -> None:
    assert platform_role_is_full_admin(PlatformRole.SUPER_ADMIN)
    assert not platform_role_is_full_admin(PlatformRole.CUSTOMER)


def test_transitions_table_non_empty() -> None:
    assert len(ALLOWED_LIFECYCLE_TRANSITIONS) >= 10


def test_descriptor() -> None:
    d = customer_lifecycle_descriptor()
    assert "customer_lifecycle_module_version" in d
    assert d.get("trial_period_days") == 21
    assert d.get("prompt11_status_machine") is True
