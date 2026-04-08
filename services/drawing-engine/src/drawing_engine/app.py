from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query

from drawing_engine.settings import DrawingEngineSettings, normalize_timeframe
from drawing_engine.storage.repo import DrawingRepository
from drawing_engine.worker import DrawingWorker
from shared_py.eventbus import STREAM_DRAWING_UPDATED
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)


class DrawingEngineRuntime:
    def __init__(self, settings: DrawingEngineSettings) -> None:
        self._logger = logging.getLogger("drawing_engine")
        self._settings = settings
        self._repo = DrawingRepository(settings.database_url, logger=self._logger)
        self._worker = DrawingWorker(settings, self._repo, logger=self._logger)
        self._worker_task: asyncio.Task[None] | None = None

    @property
    def repo(self) -> DrawingRepository:
        return self._repo

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(
            self._worker.run(),
            name="drawing-engine-worker",
        )
        self._worker_task.add_done_callback(self._on_worker_done)
        self._logger.info(
            "drawing-engine gestartet port=%s stream=%s group=%s",
            self._settings.drawing_engine_port,
            self._settings.drawing_stream,
            self._settings.drawing_group,
        )

    async def stop(self) -> None:
        await self._worker.stop()
        if self._worker_task is not None:
            await asyncio.gather(self._worker_task, return_exceptions=True)
        self._logger.info("drawing-engine gestoppt")

    def health_payload(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "drawing-engine",
            "port": self._settings.drawing_engine_port,
            "pipeline_expectations": {
                "ingress_stream": self._settings.drawing_stream,
                "consumer_group": self._settings.drawing_group,
                "writes_table": "app.drawings",
                "reads_tables": [
                    "app.structure_state",
                    "app.swings",
                    "tsdb.candles",
                    "tsdb.orderbook_top25",
                ],
                "publishes_stream": STREAM_DRAWING_UPDATED,
                "upstream_services": ["structure-engine"],
                "note_de": (
                    "last_drawing_skip: Ursache wenn keine Revision geschrieben wurde "
                    "(Orderbuch alt, keine Geometrie, kein Close)."
                ),
            },
            **self._worker.stats_payload(),
        }

    def _on_worker_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover
            self._logger.exception("drawing worker crashed", exc_info=exc)


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = DrawingEngineSettings()
    bootstrap_from_settings("drawing-engine", settings)
    runtime = DrawingEngineRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="drawing-engine",
        version="0.1.0",
        description="Versionierte Chart-Drawings aus Struktur + Orderbook.",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return runtime.health_payload()

    @app.get("/drawings/latest")
    def drawings_latest(
        symbol: str = Query(...),
        timeframe: str = Query(...),
    ) -> dict[str, object]:
        tf = normalize_timeframe(timeframe)
        try:
            rows = runtime.repo.fetch_latest_active_records(symbol=symbol, timeframe=tf)
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": f"drawings lookup failed: {exc}"},
            ) from exc
        return {"status": "ok", "symbol": symbol, "timeframe": tf, "drawings": rows}

    @app.get("/drawings/history")
    def drawings_history(parent_id: str = Query(..., min_length=1)) -> dict[str, object]:
        try:
            rows = runtime.repo.fetch_history(parent_id=parent_id)
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": f"history lookup failed: {exc}"},
            ) from exc
        if not rows:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "parent_id nicht gefunden"},
            )
        return {"status": "ok", "parent_id": parent_id, "revisions": rows}

    @app.get("/ready")
    def ready() -> dict[str, object]:
        parts = {
            "postgres": check_postgres(settings.database_url),
            "redis": check_redis_url(settings.redis_url),
        }
        parts = append_peer_readiness_checks(
            parts,
            settings.readiness_require_urls_raw,
            timeout_sec=float(settings.readiness_peer_timeout_sec),
        )
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    instrument_fastapi(app, "drawing-engine")
    return app


app = create_app()
