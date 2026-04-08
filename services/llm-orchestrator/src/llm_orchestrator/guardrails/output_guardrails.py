from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from llm_orchestrator.exceptions import GuardrailViolation

# Volle Pruefung: Operator-/Strategie-Erklaerung (Policy gegen Imperative/Garantien).
_FULL_TASKS = frozenset(
    {
        "operator_explain",
        "safety_incident_diagnosis",
        "strategy_signal_explain",
        "ai_strategy_proposal_draft",
        "admin_operations_assist",
        "strategy_signal_assist",
        "customer_onboarding_assist",
        "support_billing_assist",
    }
)

# Überall: keine Geheimnis-Leaks im Klartext (heuristisch).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[a-zA-Z0-9]{10,}\b", re.I),
    re.compile(r"\bOPENAI_API_KEY\s*[:=]\s*\S+", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBEGIN\s+(RSA\s+)?PRIVATE\s+KEY\b", re.I),
)

# Deutsch / gemischt — Unterstrings (case-insensitive).
_FORBIDDEN_SUBSTRINGS_FULL: tuple[str, ...] = (
    "gewinngarantie",
    "garantierter gewinn",
    "garantierte rendite",
    "ohne risiko garantiert",
    "gewinn ohne risiko",
    "kaufe jetzt",
    "kauf jetzt",
    "verkaufe jetzt",
    "verkauf jetzt",
    "lege jetzt eine order",
    "order jetzt platzieren",
    "ignoriere das risk",
    "ignoriere risk-gate",
    "umgehe das gate",
    "umgehung des gates",
    "privileg erweitern",
    "als super-admin",
    "vollzugriff ohne freigabe",
    "deaktiviere die authentifizierung",
    "deaktiviere authentifizierung",
    "umgehe die authentifizierung",
    "admin passwort",
    "zeig mir den jwt",
    "hier der api key",
    "internal_api_key",
    "x-internal-service-key",
    "gib mir admin",
    "ohne freigabe admin",
)


def _iter_text_blobs(obj: Any, *, max_depth: int = 14) -> Iterator[str]:
    if max_depth <= 0:
        return
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_text_blobs(v, max_depth=max_depth - 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_text_blobs(v, max_depth=max_depth - 1)


def _scan_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def _scan_full(text: str) -> list[str]:
    low = text.lower()
    hits: list[str] = []
    for sub in _FORBIDDEN_SUBSTRINGS_FULL:
        if sub.lower() in low:
            hits.append(f"substring:{sub}")
    return hits


def validate_task_output(result: dict[str, Any], *, task_type: str | None) -> None:
    """
    Nach JSON-Schema-Validierung: blockiert offensichtliche Policy-Verstöße.
    Wirft GuardrailViolation → HTTP 422 im API-Layer.
    """
    codes: list[str] = []

    for blob in _iter_text_blobs(result):
        for h in _scan_secrets(blob):
            codes.append(f"secret_pattern:{h}")

    if task_type in _FULL_TASKS:
        if result.get("execution_authority") not in (None, "none"):
            codes.append("execution_authority_must_be_none")
        for blob in _iter_text_blobs(result):
            codes.extend(_scan_full(blob))

    if codes:
        raise GuardrailViolation(
            "guardrail_failed",
            codes=codes,
        )
