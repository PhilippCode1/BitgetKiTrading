from __future__ import annotations

# ruff: noqa: E402, I001 — Bootstrap-Reihenfolge / Import-Blocks
import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI


def _ensure_monorepo_root() -> None:
    root = Path(__file__).resolve().parents[4]
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)


_ensure_monorepo_root()

from monitor_engine.api.routes_health import router as health_router
from monitor_engine.api.routes_ops import router as ops_router
from monitor_engine.config import MonitorEngineSettings
from monitor_engine.scheduler.loop import MonitorScheduler
from shared_py.eventbus import RedisStreamBus
from shared_py.observability import instrument_fastapi

logger = logging.getLogger("monitor_engine.app")


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = MonitorEngineSettings()
    bootstrap_from_settings("monitor-engine", settings)
    bus = RedisStreamBus.from_url(
        settings.redis_url,
        dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
    )
    scheduler = MonitorScheduler(settings)
    scheduler.bind_bus(bus)
    loop_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal loop_task
        app.state.settings = settings
        app.state.scheduler = scheduler
        app.state.bus = bus
        app.state.boot_ts_ms = int(time.time() * 1000)
        loop_task = asyncio.create_task(scheduler.run_forever(), name="monitor-scheduler")
        logger.info("monitor-engine started")
        yield
        if loop_task is not None:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
        logger.info("monitor-engine stopped")

    app = FastAPI(title="monitor-engine", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(ops_router)
    instrument_fastapi(app, "monitor-engine")
    return app


app = create_app()
