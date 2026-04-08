"""Strukturierte Log-Felder fuer externe Provider (ohne Secrets)."""

from __future__ import annotations

from typing import Any


def provider_log_extra(
    *,
    provider: str,
    event: str,
    http_status: int | None = None,
    exchange_mode: str | None = None,
    provider_error_code: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """
    Fuer logger.info/warning(..., extra=provider_log_extra(...)).

    Prefix ``provider_`` vermeidet Kollisionen mit LogRecord-Standardfeldern.
    """
    d: dict[str, Any] = {
        "provider_name": provider,
        "provider_event": event,
    }
    if http_status is not None:
        d["provider_http_status"] = http_status
    if exchange_mode:
        d["provider_exchange_mode"] = exchange_mode
    if provider_error_code:
        d["provider_error_code"] = provider_error_code[:64]
    if symbol:
        d["provider_symbol"] = symbol[:64]
    return d
