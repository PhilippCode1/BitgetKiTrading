from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from news_engine.api.routes_scoring import build_scoring_router
from news_engine.config import NewsEngineSettings
from news_engine.storage.repo import NewsRepository
from news_engine.social.worker import SocialStreamWorker
from news_engine.worker import NewsIngestWorker
from shared_py.eventbus import RedisStreamBus
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)


def _ensure_shared_py_path() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    if sp.is_dir():
        s = str(sp)
        if s not in sys.path:
            sys.path.insert(0, s)


_ensure_shared_py_path()


class NewsEngineRuntime:
    def __init__(self, settings: NewsEngineSettings) -> None:
        self._logger = logging.getLogger("news_engine")
        self._settings = settings
        self._repo = NewsRepository(settings.database_url, logger_=self._logger)
        self._bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
        )
        self._worker = NewsIngestWorker(settings, self._repo, self._bus, logger=self._logger)
        self._social = SocialStreamWorker(settings, self._bus, logger_=self._logger)

    @property
    def repo(self) -> NewsRepository:
        return self._repo

    @property
    def worker(self) -> NewsIngestWorker:
        return self._worker

    @property
    def bus(self) -> RedisStreamBus:
        return self._bus

    @property
    def settings(self) -> NewsEngineSettings:
        return self._settings

    def health_payload(self) -> dict[str, object]:
        db_ok = False
        redis_ok = False
        try:
            with self._repo._connect() as conn:
                conn.execute("SELECT 1")
            db_ok = True
        except Exception:
            pass
        try:
            redis_ok = bool(self._bus.ping())
        except Exception:
            pass
        return {
            "status": "ok" if db_ok and redis_ok else "degraded",
            "service": "news-engine",
            "port": self._settings.news_engine_port,
            "database_ok": db_ok,
            "redis_ok": redis_ok,
            **self._worker.stats_payload(),
            **self._social.stats_payload(),
        }


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = NewsEngineSettings()
    bootstrap_from_settings("news-engine", settings)
    runtime = NewsEngineRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime._worker.start_background()
        await runtime._social.start_background()
        try:
            yield
        finally:
            await runtime._social.stop()
            await runtime._worker.stop()

    app = FastAPI(
        title="news-engine",
        version="0.1.0",
        description="News-Ingestion (Prompt 15) + Scoring (Prompt 17).",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return runtime.health_payload()

    @app.post("/ingest/now")
    async def ingest_now() -> dict[str, object]:
        stats = await asyncio.to_thread(runtime.worker.run_ingestion_once)
        return {"status": "ok", **stats}

    @app.get("/news/latest")
    def news_latest(limit: int = 20) -> dict[str, object]:
        rows = runtime.repo.list_latest(limit=min(max(limit, 1), 100))
        return {"status": "ok", "items": rows}

    app.include_router(build_scoring_router(runtime))

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

    instrument_fastapi(app, "news-engine")
    return app


app = create_app()
