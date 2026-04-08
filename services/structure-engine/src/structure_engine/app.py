from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query

from structure_engine.settings import StructureEngineSettings, normalize_timeframe
from structure_engine.storage.repo import StructureRepository
from structure_engine.worker import StructureWorker
from shared_py.eventbus import STREAM_STRUCTURE_UPDATED
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)


class StructureEngineRuntime:
    def __init__(self, settings: StructureEngineSettings) -> None:
        self._logger = logging.getLogger("structure_engine")
        self._settings = settings
        self._repo = StructureRepository(settings.database_url, logger=self._logger)
        self._worker = StructureWorker(settings, self._repo, logger=self._logger)
        self._worker_task: asyncio.Task[None] | None = None

    @property
    def repo(self) -> StructureRepository:
        return self._repo

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(
            self._worker.run(),
            name="structure-engine-worker",
        )
        self._worker_task.add_done_callback(self._on_worker_done)
        self._logger.info(
            "structure-engine gestartet port=%s stream=%s group=%s consumer=%s",
            self._settings.structure_engine_port,
            self._settings.structure_stream,
            self._settings.structure_group,
            self._settings.structure_consumer,
        )

    async def stop(self) -> None:
        await self._worker.stop()
        if self._worker_task is not None:
            await asyncio.gather(self._worker_task, return_exceptions=True)
        self._logger.info("structure-engine gestoppt")

    def health_payload(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "structure-engine",
            "port": self._settings.structure_engine_port,
            "pipeline_expectations": {
                "ingress_stream": self._settings.structure_stream,
                "consumer_group": self._settings.structure_group,
                "writes_tables": [
                    "app.structure_state",
                    "app.structure_events",
                    "app.swings",
                ],
                "publishes_stream": STREAM_STRUCTURE_UPDATED,
                "upstream": ["tsdb.candles", "features.candle_features (ATR, optional Fallback)"],
                "note_de": (
                    "last_structure_skip erklaert letzten Skip (z. B. insufficient_candles). "
                    "Redis-Lag: XREADGROUP auf ingress_stream pruefen."
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
            self._logger.exception("structure worker crashed", exc_info=exc)


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = StructureEngineSettings()
    bootstrap_from_settings("structure-engine", settings)
    runtime = StructureEngineRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="structure-engine",
        version="0.1.0",
        description="Swings, Trend/BOS/CHOCH, Kompression, Breakouts.",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return runtime.health_payload()

    @app.get("/structure/latest")
    def structure_latest(
        symbol: str = Query(...),
        timeframe: str = Query(...),
    ) -> dict[str, object]:
        tf = normalize_timeframe(timeframe)
        try:
            state = runtime.repo.get_latest_structure_state(symbol=symbol, timeframe=tf)
            swings = runtime.repo.fetch_recent_swing_ids(symbol=symbol, timeframe=tf, limit=12)
            events = runtime.repo.fetch_recent_structure_events(
                symbol=symbol, timeframe=tf, limit=15
            )
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "error",
                    "message": f"structure lookup failed: {exc}",
                },
            ) from exc
        if state is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "structure_state noch nicht vorhanden",
                },
            )
        return {
            "status": "ok",
            "symbol": symbol,
            "timeframe": tf,
            "state": state,
            "swings": swings,
            "recent_events": events,
        }

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

    instrument_fastapi(app, "structure-engine")
    return app


app = create_app()
