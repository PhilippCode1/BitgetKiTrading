"""
SLO-Metriken: Slow-Request-Trace (CRITICAL) und Prometheus-/metrics-Exposure.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared_py.observability.metrics import instrument_fastapi


def _minimal_slo_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def request_id_middleware(request, call_next):
        incoming = (request.headers.get("x-request-id") or "").strip()
        rid = incoming or str(uuid.uuid4())
        request.state.request_id = rid
        return await call_next(request)

    # Nach request_id, wie im Gateway: aussen zuletzt registrierte HTTP-Middleware
    instrument_fastapi(app, "api-gateway")

    @app.get("/_internal/slo-mock-slow")
    async def _slow() -> dict[str, str]:
        await asyncio.sleep(1.5)
        return {"ok": "1"}

    return app


def test_slow_request_trace_critical_includes_request_id(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATEWAY_SLOW_REQUEST_TRACE", "1")
    monkeypatch.setenv("GATEWAY_SLOW_REQUEST_TRACE_SEC", "1.0")
    caplog.set_level(logging.CRITICAL)
    app = _minimal_slo_app()
    rid = "test-request-id-slo-7f2a"
    with TestClient(app) as client:
        r = client.get("/_internal/slo-mock-slow", headers={"X-Request-ID": rid})
    assert r.status_code == 200
    joined = " ".join(f"{rec.name} {rec.getMessage()}" for rec in caplog.records)
    assert "CRITICAL_WARNING" in joined
    assert "slow_request_trace" in joined
    assert rid in joined
    assert "/_internal/slo-mock-slow" in joined


def test_metrics_exposes_slo_and_histogram() -> None:
    app = _minimal_slo_app()
    with TestClient(app) as client:
        client.get("/_internal/slo-mock-slow", headers={"X-Request-ID": "m"})
        m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    assert "http_slo_responses_total" in body
    assert "http_request_duration_seconds" in body
