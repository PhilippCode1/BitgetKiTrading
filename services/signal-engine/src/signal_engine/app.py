from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from signal_engine.api import (
    build_explain_router,
    build_health_router,
    build_signals_router,
)
from signal_engine.config import SignalEngineSettings
from signal_engine.service import SignalEngineService
from signal_engine.storage.explanations_repo import ExplanationRepository
from signal_engine.storage.repo import SignalRepository
from signal_engine.worker import SignalWorker
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)


class SignalEngineRuntime:
    def __init__(self, settings: SignalEngineSettings) -> None:
        self._logger = logging.getLogger("signal_engine")
        self._settings = settings
        self._repo = SignalRepository(
            settings.database_url,
            logger=self._logger,
            model_registry_v2_enabled=settings.model_registry_v2_enabled,
            model_calibration_required=settings.model_calibration_required,
            model_champion_name=settings.model_champion_name,
            model_registry_scoped_slots_enabled=settings.model_registry_scoped_slots_enabled,
        )
        self._explain_repo = ExplanationRepository(
            settings.database_url, logger=self._logger
        )
        self._service = SignalEngineService(
            settings, self._repo, self._explain_repo, logger=self._logger
        )
        self._worker = SignalWorker(settings, self._service, logger=self._logger)
        self._worker_task: asyncio.Task[None] | None = None

    @property
    def repo(self) -> SignalRepository:
        return self._repo

    @property
    def explain_repo(self) -> ExplanationRepository:
        return self._explain_repo

    def health_payload(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "signal-engine",
            "port": self._settings.signal_engine_port,
            **self._worker.stats_payload(),
        }

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(
            self._worker.run(),
            name="signal-engine-worker",
        )
        self._worker_task.add_done_callback(self._on_worker_done)
        self._logger.info(
            "signal-engine gestartet port=%s stream=%s",
            self._settings.signal_engine_port,
            self._settings.signal_stream,
        )

    async def stop(self) -> None:
        await self._worker.stop()
        if self._worker_task is not None:
            await asyncio.gather(self._worker_task, return_exceptions=True)
        self._logger.info("signal-engine gestoppt")

    def _on_worker_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover
            self._logger.exception("signal worker crashed", exc_info=exc)


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = SignalEngineSettings()
    bootstrap_from_settings("signal-engine", settings)
    runtime = SignalEngineRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="signal-engine",
        version="0.1.0",
        description="Deterministisches Scoring V1 (6 Schichten).",
        lifespan=lifespan,
    )
    app.include_router(
        build_health_router(health_payload_fn=runtime.health_payload),
    )
    app.include_router(build_signals_router(repo=runtime.repo))
    app.include_router(
        build_explain_router(repo=runtime.repo, explain_repo=runtime.explain_repo),
    )

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

    instrument_fastapi(app, "signal-engine")
    return app


app = create_app()
