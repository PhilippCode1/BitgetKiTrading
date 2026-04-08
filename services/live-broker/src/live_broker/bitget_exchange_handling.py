"""Abbildung Bitget-Fehler -> Retry/Security/Operator (Prompt 15)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from live_broker.private_rest import BitgetErrorClassification

ExchangeHandling = Literal[
    "retryable",
    "non_retryable",
    "security_blocker",
    "operator_intervention",
]


def exchange_handling_for_classification(classification: "BitgetErrorClassification") -> ExchangeHandling:
    if classification in (
        "rate_limit",
        "transport",
        "server",
        "circuit_open",
        "timestamp",
    ):
        return "retryable"
    if classification in ("auth", "permission"):
        return "security_blocker"
    if classification == "operator_intervention":
        return "operator_intervention"
    if classification in (
        "clock_skew",
        "validation",
        "not_found",
        "conflict",
        "duplicate",
        "service_disabled",
        "kill_switch",
        "unknown",
    ):
        return "non_retryable"
    return "non_retryable"
