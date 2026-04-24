from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from starlette.responses import Response

from inference_server import inference_telemetry
from inference_server.grpc_servicer import TimesFmInferenceServicer

logger = logging.getLogger("inference_server.health")

_METRICS_INTERVAL_SEC = 1.0


def create_app(
    *,
    servicer: TimesFmInferenceServicer | None = None,
) -> FastAPI:
    if servicer is not None:
        inference_telemetry.set_queue_depth_getter(servicer.get_batch_buffer_depth)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        async def _poll() -> None:
            while True:
                try:
                    await asyncio.to_thread(inference_telemetry.refresh_all_metrics)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("metrics refresh: %s", exc)
                await asyncio.sleep(_METRICS_INTERVAL_SEC)

        task = asyncio.create_task(_poll(), name="p77-gpu-metrics")
        app.state.metrics_task = task
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            app.state.metrics_task = None
            inference_telemetry.set_queue_depth_getter(None)

    app = FastAPI(
        title="inference-server",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "inference-server"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        return {"ready": True, "service": "inference-server"}

    @app.get("/metrics")
    def metrics() -> Response:
        body, ct = inference_telemetry.render_metrics()
        return Response(content=body, media_type=ct)

    return app
