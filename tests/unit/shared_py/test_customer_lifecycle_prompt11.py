"""Tests Prompt-11-Statusmaschine (shared_py.customer_lifecycle)."""

from __future__ import annotations

from shared_py.customer_lifecycle import (
    CustomerLifecycleStatus,
    LifecyclePhase,
    TransitionActor,
    allowed_prompt11_targets,
    customer_commercial_gates_for_prompt11,
    derive_capabilities_from_prompt11,
    internal_snapshot_from_prompt11,
    is_prompt11_transition_allowed,
    lifecycle_phase_to_prompt11,
    trial_duration_days,
)
from shared_py.product_policy import live_trading_allowed, trial_period_days


def test_trial_duration_matches_product_policy() -> None:
    assert trial_duration_days() == trial_period_days()


def test_live_blocked_until_live_approved() -> None:
    g = customer_commercial_gates_for_prompt11(
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        trial_clock_active=False,
    )
    assert not live_trading_allowed(g)
    g2 = customer_commercial_gates_for_prompt11(
        CustomerLifecycleStatus.LIVE_APPROVED,
        trial_clock_active=False,
    )
    assert live_trading_allowed(g2)


def test_trial_active_clock_gates_demo_only() -> None:
    g_on = customer_commercial_gates_for_prompt11(
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        trial_clock_active=True,
    )
    assert g_on.trial_active and not g_on.contract_accepted
    g_off = customer_commercial_gates_for_prompt11(
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        trial_clock_active=False,
    )
    assert not g_off.trial_active


def test_admin_may_grant_live() -> None:
    assert is_prompt11_transition_allowed(
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
        TransitionActor.ADMIN,
    )
    assert not is_prompt11_transition_allowed(
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
        TransitionActor.USER,
    )


def test_user_may_open_contract_from_trial() -> None:
    assert is_prompt11_transition_allowed(
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        CustomerLifecycleStatus.CONTRACT_PENDING,
        TransitionActor.USER,
    )


def test_system_may_complete_contract_sign_from_pending() -> None:
    assert is_prompt11_transition_allowed(
        CustomerLifecycleStatus.CONTRACT_PENDING,
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        TransitionActor.SYSTEM,
    )


def test_suspended_restore_requires_admin_and_previous() -> None:
    assert is_prompt11_transition_allowed(
        CustomerLifecycleStatus.SUSPENDED,
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        TransitionActor.ADMIN,
        suspended_previous=CustomerLifecycleStatus.TRIAL_ACTIVE,
    )
    assert not is_prompt11_transition_allowed(
        CustomerLifecycleStatus.SUSPENDED,
        CustomerLifecycleStatus.LIVE_APPROVED,
        TransitionActor.ADMIN,
        suspended_previous=CustomerLifecycleStatus.TRIAL_ACTIVE,
    )


def test_allowed_targets_includes_suspend_for_admin() -> None:
    t = allowed_prompt11_targets(
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        TransitionActor.ADMIN,
    )
    assert CustomerLifecycleStatus.SUSPENDED in t


def test_capabilities_trial_full_demo_no_live() -> None:
    cap = derive_capabilities_from_prompt11(
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        email_verified=True,
        trial_clock_active=True,
    )
    assert cap.demo_trading
    assert cap.telegram_info_messages
    assert not cap.execute_live_orders


def test_internal_snapshot_contract_waiting_maps_live_prepared() -> None:
    snap = internal_snapshot_from_prompt11(
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        email_verified=True,
    )
    assert snap.phase == LifecyclePhase.LIVE_PREPARED


def test_phase_mapping_roundtrip_smoke() -> None:
    assert (
        lifecycle_phase_to_prompt11(LifecyclePhase.TRIAL_ACTIVE)
        == CustomerLifecycleStatus.TRIAL_ACTIVE
    )
