from __future__ import annotations

from typing import Any, Literal

from shared_py.llm_assist_context import filter_assist_context_payload

AssistRole = Literal[
    "admin_operations",
    "strategy_signal",
    "customer_onboarding",
    "support_billing",
    "ops_risk",
]

_ROLE_TO_TASK: dict[str, str] = {
    "admin_operations": "admin_operations_assist",
    "strategy_signal": "strategy_signal_assist",
    "customer_onboarding": "customer_onboarding_assist",
    "support_billing": "support_billing_assist",
    "ops_risk": "ops_risk_assist",
}


def task_type_for_role(role: str) -> str:
    if role not in _ROLE_TO_TASK:
        raise ValueError(f"Unbekannte Assistenz-Rolle: {role}")
    return _ROLE_TO_TASK[role]


def filter_context_for_role(role: str, context_json: dict[str, Any]) -> dict[str, Any]:
    """Entfernt nicht freigegebene Top-Level-Keys (Defense in Depth nach Gateway)."""
    try:
        return filter_assist_context_payload(role, context_json)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
