"""
Zentrale Bitget-v2-REST-Fehlerabbildung (private/signierte Calls).

Klassifikation wird vom live-broker `BitgetPrivateRestClient` und von Tests genutzt.
Keine Netzwerk- oder httpx-Abhaengigkeit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shared_py.resilience import is_retryable_http_status

BitgetErrorClassification = Literal[
    "auth",
    "permission",
    "timestamp",
    "clock_skew",
    "rate_limit",
    "duplicate",
    "not_found",
    "conflict",
    "validation",
    "transport",
    "server",
    "circuit_open",
    "service_disabled",
    "kill_switch",
    "operator_intervention",
    "unknown",
]

_AUTH_CODES = frozenset({"40002", "40003", "40009", "40011", "40036"})
_PERMISSION_CODES = frozenset({"40014", "40025", "40040", "40301"})
_TIMESTAMP_CODES = frozenset({"40005", "40008", "40078", "40079"})
_DUPLICATE_CODES = frozenset({"01003"})
_NOT_FOUND_CODES = frozenset({"22001", "31007", "31054", "40109", "43001", "43004"})
_CONFLICT_CODES = frozenset({"22003", "40923", "40939"})
_VALIDATION_CODES = frozenset(
    {
        "40304",
        "40305",
        "40402",
        "40404",
        "40706",
        "22034",
        "40034",
        "43006",
        "43007",
        "43008",
        "43009",
        "45109",
        "45110",
    }
)
_OPERATOR_INTERVENTION_CODES = frozenset(
    {
        "40007",
        "40010",
        "40013",
        "40015",
        "40018",
        "40019",
        "32003",
        "32004",
    }
)


@dataclass(frozen=True)
class BitgetClassifiedRestFailure:
    classification: BitgetErrorClassification
    retryable: bool
    exchange_code: str | None
    exchange_msg: str
    diagnostic_message: str


def classify_bitget_private_rest_failure(
    *,
    http_status: int,
    payload: dict[str, object],
    fallback_message: str,
) -> BitgetClassifiedRestFailure:
    """
    Mappt HTTP-Status und Bitget-JSON (`code`, `msg`) auf interne Klassifikation.

    `payload` ist typischerweise die ganze JSON-Antwort; fehlt `code`, wird er aus HTTP
    abgeleitet wo moeglich.
    """
    exchange_code_raw = payload.get("code")
    if exchange_code_raw in (None, ""):
        exchange_code = None
    else:
        exchange_code = str(exchange_code_raw).strip()
    exchange_msg = str(payload.get("msg") or fallback_message)

    classification: BitgetErrorClassification = "unknown"
    retryable = False

    if http_status == 429 or exchange_code == "429":
        classification = "rate_limit"
        retryable = True
    elif is_retryable_http_status(http_status):
        classification = "server"
        retryable = True
    elif http_status == 401 and not exchange_code:
        classification = "auth"
    elif http_status == 403 and not exchange_code:
        classification = "permission"
    elif exchange_code in _TIMESTAMP_CODES:
        classification = "timestamp"
        retryable = True
    elif exchange_code in _OPERATOR_INTERVENTION_CODES:
        classification = "operator_intervention"
    elif exchange_code in _AUTH_CODES:
        classification = "auth"
    elif exchange_code in _PERMISSION_CODES:
        classification = "permission"
    elif exchange_code in _DUPLICATE_CODES:
        classification = "duplicate"
    elif exchange_code in _NOT_FOUND_CODES:
        classification = "not_found"
    elif exchange_code in _CONFLICT_CODES:
        classification = "conflict"
    elif exchange_code in _VALIDATION_CODES:
        classification = "validation"
    elif http_status >= 400:
        classification = "server" if http_status >= 500 else "unknown"
        retryable = http_status >= 500

    diagnostic_message = (
        f"{fallback_message}: classification={classification}"
        f" http_status={http_status} code={exchange_code} msg={exchange_msg}"
    )
    return BitgetClassifiedRestFailure(
        classification=classification,
        retryable=retryable,
        exchange_code=exchange_code,
        exchange_msg=exchange_msg,
        diagnostic_message=diagnostic_message,
    )
