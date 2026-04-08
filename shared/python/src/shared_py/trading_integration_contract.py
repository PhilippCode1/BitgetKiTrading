"""
Trading-, API-, Telegram- und Sicherheitskontrakt (Modul Mate GmbH).

Bezug: docs/TRADING_INTEGRATION_SECURITY_MODUL_MATE.md (Prompt 7).

Definiert Begriffe, Pflicht-Audit-Ereignisse, Sichtbarkeit, Telegram-Stufen
und Richtwerte fuer Limits/Retries. Die eigentliche Ausfuehrung liegt in Broker-Gateways.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from shared_py.product_policy import CommercialExecutionMode, CustomerCommercialGates, resolve_execution_mode

TRADING_INTEGRATION_CONTRACT_VERSION = "1.0.0"
TRADING_INTEGRATION_DOCUMENT_ID = "TRADING_INTEGRATION_SECURITY_MODUL_MATE"


class OrderConceptStage(str, Enum):
    """
    Fachliche Kette von der Marktinformation bis zur Boerse.

    Signal/Empfehlung loesen **keine** Exchange-Orders aus.
    """

    SIGNAL = "signal"
    RECOMMENDATION = "recommendation"
    USER_APPROVAL = "user_approval"
    COMMERCIAL_GATE = "commercial_gate"
    ORDER_INTENT = "order_intent"
    PRE_TRADE_VALIDATION = "pre_trade_validation"
    SUBMIT_TO_EXCHANGE_OR_SIM = "submit_to_exchange_or_sim"
    EXCHANGE_ACK = "exchange_ack"
    PARTIAL_OR_FILL = "partial_or_fill"
    CANCEL_REQUESTED = "cancel_requested"
    CANCEL_RESOLVED = "cancel_resolved"
    TERMINAL = "terminal"


class TelegramIntegrationLevel(str, Enum):
    """Wie stark Telegram in die Ausfuehrung eingreifen darf."""

    DISABLED = "disabled"
    NOTIFY_ONLY = "notify_only"
    CONFIRM_WITH_OTP = "confirm_with_otp"


class AuditVisibility(str, Enum):
    """Wer Eintraege in der Oberflaeche sieht."""

    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPPORT = "support"


class ComplianceReviewTag(str, Enum):
    """Marker fuer Stellen, die extern (Recht/Compliance) geprueft werden muessen."""

    REGULATORY_PRODUCT_CLASSIFICATION = "regulatory_product_classification"
    CLIENT_AGREEMENT_AND_RISK_DISCLOSURE = "client_agreement_and_risk_disclosure"
    CROSS_BORDER_DATA_TRANSFER = "cross_border_data_transfer"
    MARKET_ABUSE_AND_MANIPULATION = "market_abuse_and_manipulation"
    TELEGRAM_CONSENT_CHANNEL = "telegram_consent_channel"
    AUTOMATED_EXECUTION_POLICY = "automated_execution_policy"


# Zwingend zu protokollierende Ereignistypen (stabil fuer SIEM/Audit).
MANDATORY_AUDIT_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "commercial_gate_change",
        "admin_live_approval_change",
        "order_intent_received",
        "order_validation_passed",
        "order_validation_rejected",
        "order_submit_demo",
        "order_submit_live",
        "order_exchange_response",
        "order_terminal_state",
        "cancel_request",
        "cancel_result",
        "api_credential_created",
        "api_credential_rotated",
        "api_credential_revoked",
        "telegram_linked",
        "telegram_revoked",
        "telegram_otp_challenge",
        "global_trading_halt",
        "per_customer_trading_halt",
        "circuit_breaker_opened",
        "circuit_breaker_closed",
    }
)


@dataclass(frozen=True)
class ExecutionRetryPolicy:
    """Retry nur fuer als wiederholbar klassifizierte Fehler."""

    max_attempts: int = 3
    initial_backoff_ms: int = 200
    max_backoff_ms: int = 5_000
    backoff_multiplier: float = 2.0


DEFAULT_EXECUTION_RETRY_POLICY = ExecutionRetryPolicy()


@dataclass(frozen=True)
class ApiRateLimitPolicy:
    """Richtwerte; Enforcement im Gateway / Broker."""

    orders_per_minute_per_customer: int = 60
    rest_read_per_second_per_connection: int = 20
    global_orders_per_second: int = 50


DEFAULT_API_RATE_LIMITS = ApiRateLimitPolicy()


def execution_path_for_order(gates: CustomerCommercialGates) -> CommercialExecutionMode:
    """
    Kanonischer Modus fuer neue Orders — identisch zu product_policy.resolve_execution_mode.
    """
    return resolve_execution_mode(gates)


def telegram_effective_level(
    configured: TelegramIntegrationLevel,
    *,
    live_trading_allowed: bool,
) -> TelegramIntegrationLevel:
    """
    Telegram darf nie staerker sein als der kommerzielle Live-Pfad erlaubt.

    [ANNAHME] NOTIFY_ONLY und darunter bleiben bei fehlendem Live moeglich (Infos).
    """
    if configured == TelegramIntegrationLevel.DISABLED:
        return TelegramIntegrationLevel.DISABLED
    if not live_trading_allowed and configured == TelegramIntegrationLevel.CONFIRM_WITH_OTP:
        return TelegramIntegrationLevel.NOTIFY_ONLY
    return configured


def audit_event_is_mandatory(event_type: str) -> bool:
    return event_type in MANDATORY_AUDIT_EVENT_TYPES


# Roh-Fehler der Boerse: nur Admin/Support, nicht Endkunden-UI.
VISIBILITY_EXCHANGE_RAW_ERROR: Final[AuditVisibility] = AuditVisibility.ADMIN

# Verstaendliche Fehlerkurztexte: Kunde darf sehen.
VISIBILITY_CUSTOMER_ORDER_SUMMARY: Final[AuditVisibility] = AuditVisibility.CUSTOMER


def trading_integration_descriptor() -> dict[str, str | int]:
    return {
        "trading_integration_contract_version": TRADING_INTEGRATION_CONTRACT_VERSION,
        "trading_integration_document_id": TRADING_INTEGRATION_DOCUMENT_ID,
        "mandatory_audit_event_types": len(MANDATORY_AUDIT_EVENT_TYPES),
        "order_concept_stages": len(OrderConceptStage),
    }
