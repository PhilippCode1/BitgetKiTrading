from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

AUDIT_CONTRACT_VERSION = "private-audit-v1"

SECRET_KEY_MARKERS = (
    "api_key",
    "api-secret",
    "api_secret",
    "authorization",
    "jwt",
    "passphrase",
    "password",
    "secret",
    "token",
)
REDACTED = "[REDACTED]"

REQUIRED_AUDIT_FIELDS = (
    "event_id",
    "event_type",
    "timestamp",
    "git_sha",
    "service",
    "asset_symbol",
    "market_family",
    "product_type",
    "margin_coin",
    "decision_type",
    "decision",
    "reason_codes",
    "reason_text_de",
    "risk_tier",
    "liquidity_tier",
    "data_quality_status",
    "exchange_truth_status",
    "reconcile_status",
    "operator_context",
    "trace_id",
    "correlation_id",
    "no_secrets_confirmed",
)


@dataclass(frozen=True)
class AuditValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | dict | set):
        return len(value) == 0
    return False


def _key_is_secret(key: str) -> bool:
    lowered = key.lower()
    if lowered == "no_secrets_confirmed":
        return False
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _key_is_secret(str(key)):
                redacted[str(key)] = REDACTED
            else:
                redacted[str(key)] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


def payload_contains_secret_markers(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if _key_is_secret(str(key)) and item not in (None, "", REDACTED):
                return True
            if payload_contains_secret_markers(item):
                return True
        return False
    if isinstance(value, list | tuple):
        return any(payload_contains_secret_markers(item) for item in value)
    return False


def validate_private_audit_event(event: dict[str, Any]) -> AuditValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_AUDIT_FIELDS:
        if field not in event or _is_blank(event.get(field)):
            errors.append(f"missing_{field}")

    decision_type = str(event.get("decision_type") or "").strip().lower()
    if decision_type in {"live_decision", "order_decision", "asset_quarantine"}:
        for field in ("asset_symbol", "market_family", "product_type", "margin_coin"):
            if _is_blank(event.get(field)):
                errors.append(f"live_decision_missing_{field}")

    if decision_type == "order_decision":
        if _is_blank(event.get("exchange_truth_status")):
            errors.append("order_decision_missing_exchange_truth_status")
        if _is_blank(event.get("reconcile_status")):
            errors.append("order_decision_missing_reconcile_status")

    if decision_type == "risk_decision" and _is_blank(event.get("reason_codes")):
        errors.append("risk_decision_missing_reason_codes")

    if _is_blank(event.get("reason_text_de")):
        errors.append("reason_text_de_missing")

    if event.get("no_secrets_confirmed") is not True:
        errors.append("no_secrets_confirmed_not_true")

    if payload_contains_secret_markers(event):
        errors.append("secret_marker_present")

    if str(event.get("operator_context") or "").strip().lower() not in {
        "philipp",
        "owner",
        "system",
    }:
        warnings.append("operator_context_unexpected")

    return AuditValidationResult(valid=not errors, errors=list(dict.fromkeys(errors)), warnings=warnings)


def build_private_audit_event(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_secrets(payload)
    result = validate_private_audit_event(redacted)
    return {
        "schema_version": AUDIT_CONTRACT_VERSION,
        "event": redacted,
        "validation": asdict(result),
    }


def build_german_forensic_summary(event: dict[str, Any]) -> str:
    symbol = str(event.get("asset_symbol") or "unbekannt")
    decision = str(event.get("decision") or "unbekannt")
    reasons = event.get("reason_codes") or []
    reason_text = str(event.get("reason_text_de") or "").strip()
    reason_part = ", ".join(str(item) for item in reasons) if isinstance(reasons, list) else str(reasons)
    if reason_text:
        return f"Entscheidung fuer {symbol}: {decision}. Grund: {reason_text} ({reason_part})."
    return f"Entscheidung fuer {symbol}: {decision}. Grundcodes: {reason_part}."
