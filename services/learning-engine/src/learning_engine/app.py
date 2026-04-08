from __future__ import annotations

# ruff: noqa: E402, I001 — Bootstrap-Reihenfolge / Import-Blocks
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


_ensure_paths()

from learning_engine.api.routes_health import build_health_router
from learning_engine.api.routes_metrics import (
    build_learning_health_router,
    build_learning_run_router,
)
from learning_engine.api.routes_models import build_models_router
from learning_engine.api.routes_online_drift import build_online_drift_router
from learning_engine.api.routes_registry_v2 import build_registry_v2_router
from learning_engine.api.routes_patterns import build_patterns_router
from learning_engine.api.routes_recommendations import build_recommendations_router
from learning_engine.api.routes_e2e import build_e2e_router
from learning_engine.api.routes_governance import build_governance_router
from learning_engine.api.routes_research_benchmark import build_research_benchmark_router
from learning_engine.api.routes_summary import build_summary_router
from learning_engine.api.routes_trades import build_trades_router
from learning_engine.backtest.routes import build_backtests_router
from learning_engine.config import LearningEngineSettings
from learning_engine.registry import build_registry_router
from learning_engine.worker.consumer import run_consumer_loop
from shared_py.eventbus import RedisStreamBus
from shared_py.observability import instrument_fastapi


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = LearningEngineSettings()
    bootstrap_from_settings("learning-engine", settings)
    registry_bus = RedisStreamBus.from_url(
        settings.redis_url,
        dedupe_ttl_sec=0,
        default_block_ms=settings.eventbus_block_ms,
        default_count=settings.eventbus_count,
    )
    stop = threading.Event()
    thread: threading.Thread | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal thread
        stop.clear()
        thread = threading.Thread(
            target=run_consumer_loop,
            args=(settings, stop),
            name="learning-engine-consumer",
            daemon=True,
        )
        thread.start()
        try:
            yield
        finally:
            stop.set()
            if thread is not None:
                thread.join(timeout=8.0)

    app = FastAPI(
        title="learning-engine",
        version="0.1.0",
        description="Trade feedback collector; E2E-Lernrecords (learn.e2e_decision_records).",
        lifespan=lifespan,
    )
    app.include_router(build_health_router(settings))
    app.include_router(build_learning_health_router(settings, registry_bus))
    app.include_router(build_trades_router(settings))
    app.include_router(build_e2e_router(settings))
    app.include_router(build_summary_router(settings))
    app.include_router(build_registry_router(settings, registry_bus))
    app.include_router(build_learning_run_router(settings))
    app.include_router(build_patterns_router(settings))
    app.include_router(build_recommendations_router(settings))
    app.include_router(build_backtests_router(settings))
    app.include_router(build_models_router(settings))
    app.include_router(build_governance_router(settings))
    app.include_router(build_registry_v2_router(settings))
    app.include_router(build_online_drift_router(settings))
    app.include_router(build_research_benchmark_router(settings))
    instrument_fastapi(app, "learning-engine")
    return app


app = create_app()
