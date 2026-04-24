"""
Prometheus-Metriken und FastAPI-Instrumentierung (offizieller prometheus_client).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.requests import Request

_LOG = logging.getLogger("shared_py.observability.http")

# Gateway-SLO: Histogram fuer Prometheus p95/Quantile; Buckets in Sekunden
# (PLAN: [0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0]; +Inf ergaenzt prometheus_client).
_HTTP_DURATION_BUCKETS: tuple[float, ...] = (
    0.05,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
)

_REQUESTS = Counter(
    "http_requests_total",
    "HTTP-Anfragen (Methode + status_class, kompatibel)",
    ["service", "method", "status_class"],
)

# SLO: 2xx/3xx/4xx/5xx je Routen-Gruppe (niedrige Cardinality) fuer Fehlerquoten-Alarme
_HTTP_SLO = Counter(
    "http_slo_responses_total",
    "HTTP-Antworten nach Routen-Gruppe (http_route) und Statuskategorie (2xx,3xx,4xx,5xx).",
    ["service", "http_route", "code_class"],
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

def _env_float(name: str, default: str) -> float:
    try:
        return max(0.0, float((os.environ.get(name) or default) or 0.0))
    except (TypeError, ValueError):
        return max(0.0, float(default))

_LO_SLO = logging.getLogger("api_gateway.slo")


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


def _slo_code_class(status_code: int) -> str:
    if 100 <= status_code < 200:
        return "1xx"
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def _request_full_path_for_slo(request: Request) -> str:
    p = (request.url.path or "/") or "/"
    q = (getattr(request.url, "query", None) or "").strip()
    return f"{p}?{q}" if q else p


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
    try:
        _t = asyncio.current_task()
        if _t is not None:
            _t.set_name(f"worker_heartbeat:{service_name}")
    except Exception:
        pass
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
    *,
    sn: str,
    method: str,
    path: str,
    status_code: int,
    duration_sec: float,
    request: Request | None = None,
) -> None:
    http_route = http_route_group(path)
    status_class = f"{status_code // 100}xx"
    slob = _slo_code_class(status_code)
    _REQUESTS.labels(sn, method, status_class).inc()
    _HTTP_DUR.labels(sn, http_route).observe(duration_sec)
    _HTTP_SLO.labels(sn, http_route, slob).inc()
    if 400 <= status_code < 500:
        _REQUEST_ERRORS.labels(sn, http_route, "4xx").inc()
    elif status_code >= 500:
        _ERRORS.labels(sn).inc()
        _REQUEST_ERRORS.labels(sn, http_route, "5xx").inc()
    _did_critical_slow = False
    slow_log_sec = _env_float("SLOW_REQUEST_WARNING_SEC", "1.0")
    slow_trace_sec = _env_float("GATEWAY_SLOW_REQUEST_TRACE_SEC", "1.0")
    trace_on = (os.environ.get("GATEWAY_SLOW_REQUEST_TRACE", "1") or "1").strip() in (
        "1",
        "true",
        "True",
        "yes",
        "on",
    )
    rid: str | None = None
    if request is not None:
        try:
            v = getattr(request.state, "request_id", None)
            rid = str(v) if v is not None else None
        except (AttributeError, TypeError, RuntimeError):
            rid = None
    if (
        request is not None
        and trace_on
        and slow_trace_sec > 0
        and duration_sec > slow_trace_sec
    ):
        fullp = _request_full_path_for_slo(request)
        _LO_SLO.critical(
            "CRITICAL_WARNING: slow_request_trace duration_s=%.2f method=%s full_path=%s "
            "request_id=%s http_route=%s service=%s",
            float(duration_sec),
            method,
            fullp,
            str(rid) if rid is not None else "unknown",
            http_route,
            sn,
        )
        _did_critical_slow = True
    if (not _did_critical_slow) and slow_log_sec > 0 and duration_sec > slow_log_sec:
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
                request=request,
            )
            return response
        _record_http(
            sn=sn,
            method=request.method,
            path=str(request.url.path),
            status_code=500,
            duration_sec=dt,
            request=request,
        )
        if err is not None:
            raise err
        raise RuntimeError("metrics: no response and no exception")  # pragma: no cover

    app.mount("/metrics", make_asgi_app())


# ---------------------------------------------------------------------------
# Pipeline-Backpressure (Marktdaten-Feature-Pipeline, market-stream, Eventbus)
# ---------------------------------------------------------------------------
_PIPELINE_BACKPRESSURE_QUEUE: Gauge = Gauge(
    "pipeline_backpressure_queue_size",
    "Aktuelle Anzahl der Events im referenzierten Redis-Stream (Warteschlange/Backpressure).",
    ["stream"],
)
_PIPELINE_EVENT_DROP: Counter = Counter(
    "pipeline_event_drop_total",
    "Fehlgeschlagene oder explizit verworfene Marktdaten-Events (Timeout, Overflow, "
    "Publish-Fehler). Nicht: fachliches Reject/Qualitaet.",
    ["component", "reason"],
)


def set_pipeline_backpressure_queue_size(*, stream: str, size: int) -> None:
    """Aktualisiert die sichtbare Stream-Laenge (Gauge). `stream` = voller Redis-Key."""
    s = (stream or "").strip() or "unknown"
    try:
        v = int(size)
    except (TypeError, ValueError):
        v = 0
    v = max(0, v)
    _PIPELINE_BACKPRESSURE_QUEUE.labels(stream=s).set(float(v))


def inc_pipeline_event_drop(*, component: str, reason: str) -> None:
    """
    Vollzaehlig bei: Redis-Publish-Abbruch, beide Sinks weg, explizite Verwerfungen.
    reason: z. B. redis_publish_failed, dual_sink_failure, consume_timeout, buffer_overflow
    """
    c = (component or "unknown").replace("-", "_")[:64]
    r = (reason or "unknown")[:64]
    _PIPELINE_EVENT_DROP.labels(component=c, reason=r).inc()


# ---------------------------------------------------------------------------
# market-stream: VPIN / Orderflow-Toxizitaet (Rust VpinEngine via apex_core)
# ---------------------------------------------------------------------------
_VPIN_DUR_BUCKETS: tuple[float, ...] = (
    0.000_25,
    0.000_5,
    0.001,
    0.002,
    0.003,
    0.004,
    0.005,
    0.01,
    0.05,
)
_MARKET_VPIN_SCORE = Gauge(
    "market_vpin_score",
    "VPIN-/Toxicity-Score in [0,1] (rollierendes Volumen-Fenster, Rust-Indikator).",
    ["symbol"],
)
_MARKET_VPIN_INFERENCE_DURATION = Histogram(
    "market_vpin_inference_duration_seconds",
    (
        "Wall-Clock pro VPIN-Update: Trade-Batch in den Akkumulator + "
        "toxicity_score (Apex/Rust)."
    ),
    ["symbol"],
    buckets=_VPIN_DUR_BUCKETS,
)
_MARKET_VPIN_INFERENCE_SLOW = Counter(
    "market_vpin_inference_slow_total",
    (
        "VPIN-Updates >5ms (SLO-Tripwire; kein Markt-Alarm, siehe P1-Rule "
        "MarketVpinExtremeToxicity auf market_vpin_score)."
    ),
    ["symbol"],
)


def set_market_vpin_score(*, symbol: str, score: float) -> None:
    """
    Setzt die aktuelle Gauge fuer ein Symbol. Wert wird auf [0,1] begrenzt.
    """
    s = (symbol or "").strip() or "unknown"
    v = float(score)
    if not math.isfinite(v):
        v = 0.0
    v = max(0.0, min(1.0, v))
    _MARKET_VPIN_SCORE.labels(symbol=s).set(v)


def observe_market_vpin_inference(
    *, symbol: str, duration_sec: float, slow_threshold_sec: float = 0.005
) -> None:
    """
    Protokolliert die Latenz eines VPIN-Batches; zaehlt Ueberschreitungen von
    slow_threshold (Standard 5ms) in market_vpin_inference_slow_total.
    """
    s = (symbol or "").strip() or "unknown"
    ds = float(duration_sec)
    if not math.isfinite(ds) or ds < 0.0:
        ds = 0.0
    _MARKET_VPIN_INFERENCE_DURATION.labels(symbol=s).observe(ds)
    if ds > slow_threshold_sec:
        _MARKET_VPIN_INFERENCE_SLOW.labels(symbol=s).inc()
