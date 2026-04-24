"""
Hilfsmeldungen an den monitor-engine; GPU-/Warteschlangen-Metriken liegen in
``inference_telemetry`` (P77) und erscheinen am inference-server-``/metrics``.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from inference_server.config import InferenceServerSettings

logger = logging.getLogger("inference_server.monitoring")


async def report_inference_batch_metric(
    settings: InferenceServerSettings,
    *,
    batch_size: int,
    forecast_horizon: int,
    latency_ms: float,
    backend: str,
) -> None:
    """Meldet Batch-Latenz an monitor-engine (Prometheus-Histogram via FastAPI-Route)."""
    url = f"{settings.monitor_engine_base_url.rstrip('/')}/ops/inference-batch-metric"
    headers: dict[str, str] = {}
    key = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if key:
        headers["X-Internal-Service-Key"] = key
    payload = {
        "model_id": settings.timesfm_model_id[:128],
        "batch_size": int(batch_size),
        "forecast_horizon": int(forecast_horizon),
        "latency_ms": float(latency_ms),
        "backend": (backend or "unknown")[:32],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=3.0)
            if r.status_code >= 400:
                logger.warning(
                    "monitor-engine inference metric: HTTP %s %s",
                    r.status_code,
                    r.text[:200],
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("monitor-engine inference metric nicht erreichbar: %s", exc)


def schedule_batch_metric_report(
    settings: InferenceServerSettings,
    *,
    batch_size: int,
    forecast_horizon: int,
    latency_ms: float,
    backend: str,
) -> None:
    asyncio.create_task(
        report_inference_batch_metric(
            settings,
            batch_size=batch_size,
            forecast_horizon=forecast_horizon,
            latency_ms=latency_ms,
            backend=backend,
        ),
        name="inference-batch-metric",
    )
