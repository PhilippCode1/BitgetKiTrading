"""Tests fuer shared_py.trading_integration_contract (Prompt 7)."""

from __future__ import annotations

from shared_py.product_policy import CustomerCommercialGates
from shared_py.trading_integration_contract import (
    DEFAULT_API_RATE_LIMITS,
    DEFAULT_EXECUTION_RETRY_POLICY,
    MANDATORY_AUDIT_EVENT_TYPES,
    CommercialExecutionMode,
    ComplianceReviewTag,
    OrderConceptStage,
    TelegramIntegrationLevel,
    audit_event_is_mandatory,
    execution_path_for_order,
    telegram_effective_level,
    trading_integration_descriptor,
)


def test_order_stages_include_gate_before_submit() -> None:
    stages = list(OrderConceptStage)
    assert OrderConceptStage.COMMERCIAL_GATE in stages
    assert OrderConceptStage.SUBMIT_TO_EXCHANGE_OR_SIM in stages
    assert stages.index(OrderConceptStage.COMMERCIAL_GATE) < stages.index(
        OrderConceptStage.SUBMIT_TO_EXCHANGE_OR_SIM
    )


def test_execution_path_matches_product_policy() -> None:
    gates = CustomerCommercialGates(
        trial_active=True,
        contract_accepted=False,
        admin_live_trading_granted=False,
        subscription_active=False,
    )
    assert execution_path_for_order(gates) == CommercialExecutionMode.DEMO


def test_telegram_downgrade_without_live() -> None:
    assert (
        telegram_effective_level(
            TelegramIntegrationLevel.CONFIRM_WITH_OTP,
            live_trading_allowed=False,
        )
        == TelegramIntegrationLevel.NOTIFY_ONLY
    )


def test_telegram_unchanged_when_live() -> None:
    assert (
        telegram_effective_level(
            TelegramIntegrationLevel.CONFIRM_WITH_OTP,
            live_trading_allowed=True,
        )
        == TelegramIntegrationLevel.CONFIRM_WITH_OTP
    )


def test_mandatory_audit_contains_order_submit() -> None:
    assert audit_event_is_mandatory("order_submit_live")
    assert audit_event_is_mandatory("order_submit_demo")
    assert not audit_event_is_mandatory("random_noise")


def test_compliance_tags_distinct() -> None:
    assert len(ComplianceReviewTag) >= 5


def test_retry_policy_sane() -> None:
    p = DEFAULT_EXECUTION_RETRY_POLICY
    assert 1 <= p.max_attempts <= 10
    assert p.initial_backoff_ms <= p.max_backoff_ms


def test_api_limits_positive() -> None:
    lim = DEFAULT_API_RATE_LIMITS
    assert lim.orders_per_minute_per_customer > 0


def test_descriptor() -> None:
    d = trading_integration_descriptor()
    assert d["mandatory_audit_event_types"] == len(MANDATORY_AUDIT_EVENT_TYPES)
