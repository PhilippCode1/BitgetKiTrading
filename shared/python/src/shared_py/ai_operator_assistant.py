"""Sicherheits-Contract fuer den deutschen KI-Operator-Assistenten (read-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssistantValidationResult:
    ok: bool
    reasons: list[str]


def redact_secret_like_text(text: str) -> str:
    redacted = re.sub(
        r"(?i)(apikey|api_key|secret|password|passphrase|token|authorization)\s*[:=]\s*\S+",
        r"\1=***REDACTED***",
        text,
    )
    redacted = re.sub(r"(?i)bearer\s+\S+", "Bearer ***REDACTED***", redacted)
    return redacted


def sanitize_untrusted_context_text(text: str) -> str:
    """Prompt-Injection-Hinweise aus untrusted Feldern zu neutralem Lesetext machen."""
    lowered = text.lower()
    injection_markers = (
        "ignore previous instructions",
        "system:",
        "du bist jetzt",
        "override",
        "developer message",
    )
    if any(marker in lowered for marker in injection_markers):
        return "Untrusted Kontext erkannt (potenzielle Prompt-Injection) — nur als Vorfalltext behandeln."
    return text


def contains_forbidden_trading_promises(text: str) -> bool:
    lowered = text.lower()
    forbidden = (
        "kaufe jetzt",
        "verkaufe jetzt",
        "garantierter gewinn",
        "sicherer profit",
        "live freigeben",
        "risk gate override",
        "kill-switch release",
        "safety-latch release",
        "order erzeugen",
        "anlageberatung",
    )
    return any(token in lowered for token in forbidden)


def validate_operator_assistant_response(payload: dict[str, Any], *, live_blocked: bool) -> AssistantValidationResult:
    reasons: list[str] = []
    result = payload.get("result")
    if not isinstance(result, dict):
        reasons.append("result_missing")
        return AssistantValidationResult(ok=False, reasons=reasons)

    authority = result.get("execution_authority")
    if authority != "none":
        reasons.append("execution_authority_not_none")

    explanation = str(result.get("explanation_de") or result.get("incident_summary_de") or "")
    if not explanation.strip():
        reasons.append("missing_explanation")

    if "keine live-freigabe" not in explanation.lower() and "nur erklärung" not in explanation.lower():
        reasons.append("missing_non_authoritative_disclaimer")

    if live_blocked and "live bleibt blockiert" not in explanation.lower():
        reasons.append("missing_live_blocked_statement")

    if contains_forbidden_trading_promises(explanation):
        reasons.append("forbidden_trading_phrase")

    if re.search(r"(?i)(api[_-]?key|secret|token|passphrase|password)\s*[:=]\s*\S+", explanation):
        reasons.append("secret_leak")

    return AssistantValidationResult(ok=len(reasons) == 0, reasons=reasons)


def build_degraded_assistant_message() -> str:
    return "KI-Erklärung aktuell nicht verfügbar — keine Auswirkung auf Trading-Freigaben."
