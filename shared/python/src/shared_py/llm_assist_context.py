"""
Gemeinsame Kontext-Allowlists fuer die Assistenzschicht (Gateway + Orchestrator).

Nur erlaubte Top-Level-Keys werden an den Prompt durchgereicht — Defense in Depth.
"""

from __future__ import annotations

from typing import Any

# Rollen wie in API-Vertraege (BFF/Gateway/Orchestrator).
_ASSIST_CONTEXT_KEY_ALLOWLIST: dict[str, frozenset[str]] = {
    "admin_operations": frozenset(
        {
            "platform_health",
            "signals_summary",
            "orders_snapshot",
            "pnl_snapshot",
            "alerts_open",
            "contracts_summary",
            "billing_platform_snapshot",
            "help_page_excerpt",
            "operator_notes",
        }
    ),
    "strategy_signal": frozenset(
        {
            "signal_snapshot",
            "signal_history",
            "orders_readonly",
            "pnl_readonly",
            "risk_limits",
            "strategy_meta",
            "help_page_excerpt",
        }
    ),
    "customer_onboarding": frozenset(
        {
            "tenant_profile",
            "trial_status",
            "onboarding_checklist",
            "product_faq_excerpt",
            "preferences",
        }
    ),
    "support_billing": frozenset(
        {
            "tenant_billing_snapshot",
            "invoices_summary",
            "plan_snapshot",
            "payment_status",
            "usage_month",
            "help_billing_excerpt",
        }
    ),
}


def assist_roles() -> frozenset[str]:
    return frozenset(_ASSIST_CONTEXT_KEY_ALLOWLIST.keys())


def filter_assist_context_payload(
    role: str,
    context_json: dict[str, Any],
) -> dict[str, Any]:
    allowed = _ASSIST_CONTEXT_KEY_ALLOWLIST.get(role)
    if allowed is None:
        raise ValueError(f"unknown_assist_role:{role}")
    out: dict[str, Any] = {}
    for k, v in context_json.items():
        if k in allowed:
            out[k] = v
    return out
