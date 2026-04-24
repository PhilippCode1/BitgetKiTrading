"""
Prometheus-Metriken: kritische Gateway-Pfade (Muster docs/observability.md).

Gemeinsame HTTP-SLOs in ``shared_py.observability.metrics.instrument_fastapi`` (an ``/metrics``):

- ``http_request_duration_seconds`` – Histogram, Buckets
  (0,05, 0,1, 0,25, 0,5, 0,75, 1,0, 2,5, 5,0) s, Label ``http_route`` (z. B. /v1/llm, /v1/live-broker, /v1/system, …);
- ``http_slo_responses_total`` – Zaehler 1xx/2xx/3xx/4xx/5xx pro ``http_route``;
- ``http_request_errors_total`` / ``http_errors_total``;
- langsame Requests: ``CRITICAL``-Log (CRITICAL_WARNING) mit request_id, wenn Dauer
  > ``GATEWAY_SLOW_REQUEST_TRACE_SEC`` (default 1,0s).
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

_LIVE_BROKER_FWD = Counter(
    "gateway_live_broker_forward_total",
    "POST-Forward vom Gateway zum live-broker (Safety/Operator)",
    ["result"],
)

_LIVE_BROKER_LAT = Histogram(
    "gateway_live_broker_forward_latency_seconds",
    "Latenz der live-broker JSON-Forwards",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 45.0),
)

_AUTH_FAILURES = Counter(
    "gateway_auth_failures_total",
    "Authentifizierungsfehler am Gateway (Audit-Pfad)",
    ["action"],
)


def observe_live_broker_forward(*, result: str, elapsed_sec: float) -> None:
    _LIVE_BROKER_FWD.labels(result).inc()
    _LIVE_BROKER_LAT.observe(elapsed_sec)


def observe_auth_failure(action: str) -> None:
    _AUTH_FAILURES.labels(action[:64]).inc()
