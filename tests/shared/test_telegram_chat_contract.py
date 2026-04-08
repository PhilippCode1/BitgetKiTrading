from __future__ import annotations

from shared_py.telegram_chat_contract import (
    FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS,
    TELEGRAM_CHAT_CONTRACT_VERSION,
    command_contract_summary,
)


def test_contract_version_stable() -> None:
    assert TELEGRAM_CHAT_CONTRACT_VERSION == "telegram-chat-contract-v1"


def test_summary_contains_command_groups() -> None:
    s = command_contract_summary()
    assert s["contract_version"] == TELEGRAM_CHAT_CONTRACT_VERSION
    assert "/release_step1" in s["allowed_operator_commands"]
    assert "set_weight" in s["forbidden_strategy_mutation_verbs"]


def test_forbidden_verbs_cover_policy_surface() -> None:
    assert "playbook" in FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS
    assert "risk_limit" in FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS
    assert "registry_promote" in FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS
