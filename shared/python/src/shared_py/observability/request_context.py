"""HTTP Request-/Correlation-Kontext fuer Logs und ausgehende Calls (Contextvars).

Apex-Latenz-Traces (EventEnvelope.apex_trace) laufen pro Event/Request; bitte
``shared_py.observability.apex_trace`` fuer Hops und Deltas nutzen — nicht
hier, um Contextvars mit Stream-Hotpath zu vermischen.
"""

from __future__ import annotations

import contextvars
import logging

_ctx_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "obs_request_id", default=None
)
_ctx_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "obs_correlation_id", default=None
)
_ctx_incident_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "obs_incident_post_mortem_id", default=None
)
_ctx_incident_correlation: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "obs_incident_correlation_id", default=None
)


def set_request_context(*, request_id: str, correlation_id: str) -> None:
    _ctx_request_id.set(request_id)
    _ctx_correlation_id.set(correlation_id)


def clear_request_context() -> None:
    _ctx_request_id.set(None)
    _ctx_correlation_id.set(None)
    _ctx_incident_id.set(None)
    _ctx_incident_correlation.set(None)


def set_incident_context(*, post_mortem_id: str, incident_correlation_id: str) -> None:
    """Fuer P79-Post-Mortem-Logs/Outbound (Monitor-RCA, nicht pro HTTP-Request)."""
    _ctx_incident_id.set(post_mortem_id)
    _ctx_incident_correlation.set(incident_correlation_id)


def clear_incident_context() -> None:
    _ctx_incident_id.set(None)
    _ctx_incident_correlation.set(None)


def get_current_trace_ids() -> tuple[str | None, str | None]:
    """Aktuelle Request-/Correlation-ID aus dem Kontext (fuer strukturierte Logs)."""
    return _ctx_request_id.get(None), _ctx_correlation_id.get(None)


def get_outbound_trace_headers() -> dict[str, str]:
    """Header fuer interne HTTP-Calls (z. B. live-broker), leer wenn kein Kontext."""
    rid = _ctx_request_id.get(None)
    cid = _ctx_correlation_id.get(None)
    iid = _ctx_incident_id.get(None)
    icc = _ctx_incident_correlation.get(None)
    h: dict[str, str] = {}
    if rid:
        h["X-Request-ID"] = rid
    if cid:
        h["X-Correlation-ID"] = cid
    if iid:
        h["X-Incident-Post-Mortem-Id"] = iid
    if not rid and iid:
        h["X-Request-ID"] = iid
    if not cid and icc:
        h["X-Correlation-ID"] = icc
    return h


class RequestContextLoggingFilter(logging.Filter):
    """Setzt corr_request_id / corr_correlation_id auf dem LogRecord (JSON-Logs)."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = _ctx_request_id.get(None)
        cid = _ctx_correlation_id.get(None)
        if rid:
            record.corr_request_id = rid  # type: ignore[attr-defined]
        if cid:
            record.corr_correlation_id = cid  # type: ignore[attr-defined]
        return True
