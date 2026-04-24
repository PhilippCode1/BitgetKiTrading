from decimal import Decimal

from shared_py.product_policy import (
    plan_entitlement_key_enabled,
    prepaid_balance_sufficient,
)


def test_plan_entitlement_requires_explicit_true() -> None:
    assert not plan_entitlement_key_enabled({"ai_deep_analysis": False}, key="ai_deep_analysis")
    assert not plan_entitlement_key_enabled({}, key="ai_deep_analysis")
    assert plan_entitlement_key_enabled({"ai_deep_analysis": True}, key="ai_deep_analysis")


def test_prepaid_sufficient() -> None:
    assert prepaid_balance_sufficient(Decimal("10"), min_list_usd=Decimal("0"))
    assert not prepaid_balance_sufficient(Decimal("0"), min_list_usd=Decimal("0.01"))


def test_free_plan_starts_false_paid_starts_true() -> None:
    free_ej = {"llm": "none", "ai_deep_analysis": False}
    paid_ej = {"llm": "standard", "ai_deep_analysis": True}
    assert not plan_entitlement_key_enabled(free_ej, key="ai_deep_analysis")
    assert plan_entitlement_key_enabled(paid_ej, key="ai_deep_analysis")
