"""
Endgueltiger Telegram-/Chat-Vertrag (read-only + gebundene Operator-Mutationen).

Der Strategiekern (Gewichte, Playbooks, Risk-Caps, Registry, Produktions-Prompts)
ist gegen Chat-Mutation geschuetzt — nicht Safety- oder Compliance-Controls.
"""

from __future__ import annotations

from typing import Any, Final

TELEGRAM_CHAT_CONTRACT_VERSION: Final[str] = "telegram-chat-contract-v1"

# Explizit verbotene Intent-Prafixe / Kommandos (Dokumentation + Tests).
FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS: frozenset[str] = frozenset(
    {
        "set_weight",
        "set_weights",
        "model_weight",
        "playbook",
        "registry_promote",
        "promote_model",
        "risk_limit",
        "risk_cap",
        "policy_edit",
        "prompt_edit",
        "system_prompt",
        "strategy_rewrite",
        "lane_override",
    }
)

# Kanonische ausgehende Nachrichten-Typen (intel_kind / Outbox alert_type Mapping in alert-engine).
CHAT_OUTBOUND_MESSAGE_TYPES: tuple[str, ...] = (
    "pre_trade_rationale",
    "release_pending",
    "trade_open",
    "trade_close",
    "exit_rationale",
    "post_trade_review",
    "incident",
    "kill_switch",
    "safety_latch",
    # Bestehende Intel-Arten (weiterhin gueltig)
    "strategy_intent",
    "no_trade",
    "plan_summary",
    "risk_notice",
    "fill",
    "exit_result",
    "execution_update",
)

# Lesende / informative Telegram-Befehle (Allowlist-Teilmenge; Source of truth: alert_engine.telegram.commands)
READONLY_TELEGRAM_COMMANDS_DOC: frozenset[str] = frozenset(
    {
        "/help",
        "/status",
        "/mute",
        "/unmute",
        "/lastsignal",
        "/lastnews",
    }
)

OPERATOR_TELEGRAM_COMMANDS_DOC: frozenset[str] = frozenset(
    {
        "/exec_recent",
        "/exec_show",
        "/release_step1",
        "/release_confirm",
        "/release_abort",
        "/emerg_step1",
        "/emerg_confirm",
        "/emerg_abort",
    }
)


def command_contract_summary() -> dict[str, Any]:
    """Fuer Doku, Health und Audit-Metadaten."""
    return {
        "contract_version": TELEGRAM_CHAT_CONTRACT_VERSION,
        "allowed_readonly_commands": sorted(READONLY_TELEGRAM_COMMANDS_DOC),
        "allowed_operator_commands": sorted(OPERATOR_TELEGRAM_COMMANDS_DOC),
        "forbidden_strategy_mutation_verbs": sorted(FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS),
        "outbound_message_types": list(CHAT_OUTBOUND_MESSAGE_TYPES),
        "real_money_rules": {
            "bind_to_execution_or_internal_order_id": True,
            "dual_confirmation": True,
            "audit_trail": True,
            "rbac_optional_user_id_allowlist": True,
            "manual_action_token_optional_on_confirm": True,
        },
        "strategy_parallel_paths": "paper_shadow_continue",
    }
