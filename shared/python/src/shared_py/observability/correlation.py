"""Einheitliche Log-Felder fuer Korrelation (Signal, Order, Position, Alert).

Verwendung: ``logger.info("msg", extra=log_correlation_fields(...))``.
Bei JSON-Logging (``LOG_FORMAT=json``) erscheinen die Felder in der Ausgabe.
"""

from __future__ import annotations

import uuid
from typing import Any


def new_trace_id() -> str:
    return str(uuid.uuid4())


def log_correlation_fields(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
    signal_id: str | None = None,
    execution_id: str | None = None,
    internal_order_id: str | None = None,
    position_id: str | None = None,
    alert_key: str | None = None,
    event_id: str | None = None,
    symbol: str | None = None,
    gateway_audit_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Liefert ein ``extra``-Dict ohne Kollision mit LogRecord-Standardattributen."""
    out: dict[str, Any] = {}
    if request_id:
        out["corr_request_id"] = request_id
    if correlation_id:
        out["corr_correlation_id"] = correlation_id
    if trace_id:
        out["corr_trace_id"] = trace_id
    if signal_id:
        out["corr_signal_id"] = signal_id
    if execution_id:
        out["corr_execution_id"] = execution_id
    if internal_order_id:
        out["corr_internal_order_id"] = internal_order_id
    if position_id:
        out["corr_position_id"] = position_id
    if alert_key:
        out["corr_alert_key"] = alert_key
    if event_id:
        out["corr_event_id"] = event_id
    if symbol:
        out["corr_symbol"] = symbol
    if gateway_audit_id:
        out["corr_gateway_audit_id"] = gateway_audit_id
    if tenant_id:
        out["corr_tenant_id"] = tenant_id
    return out
