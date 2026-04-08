"""
Prometheus-Metriken und FastAPI-Instrumentierung (offizieller prometheus_client).
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.requests import Request

_REQUESTS = Counter(
    "http_requests_total",
    "HTTP-Anfragen",
    ["service", "method", "status_class"],
)

_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP-Latenz (Sekunden)",
    ["service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

_ERRORS = Counter(
    "http_errors_total",
    "HTTP 5xx",
    ["service"],
)

_WORKER_HEARTBEAT = Gauge(
    "worker_heartbeat_timestamp",
    "Letzter Heartbeat (Unix-Sekunden)",
    ["service"],
)


def touch_worker_heartbeat(service_name: str) -> None:
    """Worker-Schleifen koennen das periodisch setzen."""
    _WORKER_HEARTBEAT.labels(service_name).set(time.time())


def instrument_fastapi(app: Any, service_name: str) -> None:
    """
    Middleware fuer Request-Zaehler/Latenz + Mount von /metrics (make_asgi_app).
    """
    sn = service_name.replace("-", "_")

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next: Callable[[Request], Awaitable[Any]]):
        t0 = time.perf_counter()
        response = await call_next(request)
        dt = time.perf_counter() - t0
        code = response.status_code
        status_class = f"{code // 100}xx"
        _REQUESTS.labels(sn, request.method, status_class).inc()
        _LATENCY.labels(sn).observe(dt)
        if code >= 500:
            _ERRORS.labels(sn).inc()
        touch_worker_heartbeat(sn)
        return response

    app.mount("/metrics", make_asgi_app())
