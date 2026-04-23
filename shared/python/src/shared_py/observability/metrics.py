"""
Prometheus-Metriken und FastAPI-Instrumentierung (offizieller prometheus_client).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.requests import Request

_LOG = logging.getLogger("shared_py.observability.http")

# p95-nahe SLO-Granularitaet, inkl. 0,5s Schwelle; plus feine Buckets < 0,05s
_HTTP_DURATION_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.02,
    0.05,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
    7.5,
    10.0,
)

_REQUESTS = Counter(
    "http_requests_total",
    "HTTP-Anfragen",
    ["service", "method", "status_class"],
)

# Prometheus-Konvention; *_bucket fuer Histogramme in /metrics
_HTTP_DUR = Histogram(
    "http_request_duration_seconds",
    "HTTP-Zeit pro Anfrage (Sekunden)",
    ["service", "http_route"],
    buckets=_HTTP_DURATION_BUCKETS,
)

_REQUEST_ERRORS = Counter(
    "http_request_errors_total",
    "4xx- und 5xx-Antworten, gruppiert nach niedriger-Cardinality-Route",
    ["service", "http_route", "error_class"],
)

_ERRORS = Counter(
    "http_errors_total",
    "HTTP 5xx (Gesamtzaehler, nur service)",
    ["service"],
)

_WORKER_HEARTBEAT = Gauge(
    "worker_heartbeat_timestamp",
    "Letzter Heartbeat (Unix-Sekunden)",
    ["service"],
)

_SLOW_REQUEST_LOG_SEC = float(
    os.environ.get("SLOW_REQUEST_WARNING_SEC", "1.0")
)


def http_route_group(path: str) -> str:
    """
    Fasst den Pfad auf ein zweites Label unter /v1/<group>/..., sonst Top-Segment
    (niedrige Cardinality, keine ID-Pfade).
    Beispiele: /v1/llm/a -> /v1/llm, /ready -> /ready
    """
    if not path:
        return "unknown"
    p = (path or "/").split("?", 1)[0].strip() or "/"
    p = p.rstrip("/") or "/"
    if p == "/":
        return "/"
    segs = [s for s in p.split("/") if s]
    if not segs:
        return "/"
    if len(segs) >= 2 and segs[0] == "v1":
        return f"/v1/{segs[1]}"
    return f"/{segs[0]}"


def touch_worker_heartbeat(service_name: str) -> None:
    """Periodischer Heartbeat der Worker (schnell, GIL-brief, blockiert kein I/O)."""
    _WORKER_HEARTBEAT.labels(service_name).set(time.time())


async def arun_periodic_heartbeat(
    service_name: str, interval_s: float, stop_event: asyncio.Event
) -> None:
    """
    In einem eigenen Task laufen lassen: Heartbeat in festen Abstaenden, damit
    lange CPU-/DB-Abschnitte in der Worker-Hauptschleife die Prom-Gauge nicht
    veralten lassen.
    """
    while not stop_event.is_set():
        with contextlib.suppress(Exception):
            touch_worker_heartbeat(service_name)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        except TimeoutError:
            pass


def start_thread_periodic_heartbeat(
    service_name: str, interval_s: float, stop_event: threading.Event
) -> threading.Thread:
    """
    Fuer reine ``threading``-Worker (kein asyncio): Heartbeat-Thread, der nicht
    von langer Synchron-Arbeit in der Hauptroutine ausgehungert wird.
    """
    def _run() -> None:
        while not stop_event.is_set():
            with contextlib.suppress(Exception):
                touch_worker_heartbeat(service_name)
            if stop_event.wait(timeout=interval_s):
                return

    t = threading.Thread(
        target=_run, name=f"hb:{service_name}", daemon=True
    )
    t.start()
    return t


def _record_http(
    *, sn: str, method: str, path: str, status_code: int, duration_sec: float
) -> None:
    http_route = http_route_group(path)
    status_class = f"{status_code // 100}xx"
    _REQUESTS.labels(sn, method, status_class).inc()
    _HTTP_DUR.labels(sn, http_route).observe(duration_sec)
    if 400 <= status_code < 500:
        _REQUEST_ERRORS.labels(sn, http_route, "4xx").inc()
    elif status_code >= 500:
        _ERRORS.labels(sn).inc()
        _REQUEST_ERRORS.labels(sn, http_route, "5xx").inc()
    if duration_sec > _SLOW_REQUEST_LOG_SEC and _SLOW_REQUEST_LOG_SEC > 0:
        _LOG.warning(
            "Slow HTTP request: method=%s path=%s http_route=%s "
            "status=%d duration_s=%.4f service=%s",
            method,
            path,
            http_route,
            status_code,
            duration_sec,
            sn,
        )
    touch_worker_heartbeat(sn)


def instrument_fastapi(app: Any, service_name: str) -> None:
    """
    Middleware fuer Request-Zaehler, Latenz-Histogramm (inkl. SLO-Buckets),
    Fehler nach Route-Gruppe, slow-request WARNING-Log, Mount /metrics.
    """
    sn = service_name.replace("-", "_")

    @app.middleware("http")
    async def _metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Any]],
    ):
        t0 = time.perf_counter()
        err: Exception | None = None
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover
            err = exc
            response = None
        finally:
            dt = time.perf_counter() - t0
        if response is not None:
            _record_http(
                sn=sn,
                method=request.method,
                path=str(request.url.path),
                status_code=int(response.status_code),
                duration_sec=dt,
            )
            return response
        _record_http(
            sn=sn,
            method=request.method,
            path=str(request.url.path),
            status_code=500,
            duration_sec=dt,
        )
        if err is not None:
            raise err
        raise RuntimeError("metrics: no response and no exception")  # pragma: no cover

    app.mount("/metrics", make_asgi_app())
