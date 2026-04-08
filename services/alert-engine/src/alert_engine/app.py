from __future__ import annotations

# ruff: noqa: E402, I001 — Bootstrap-Reihenfolge / Import-Blocks
import logging
import sys
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

from shared_py.observability import instrument_fastapi

from alert_engine.api.routes_admin import router as admin_router
from alert_engine.api.routes_health import router as health_router
from alert_engine.api.routes_outbox import router as outbox_router
from alert_engine.api.routes_webhook import router as webhook_router
from alert_engine.config import get_settings
from alert_engine.storage.ensure_migrations import (
    count_applied_migrations,
    ensure_postgres_migrations_applied,
)
from config.bootstrap import bootstrap_from_settings

bootstrap_from_settings("alert-engine", get_settings())
from alert_engine.worker.scheduler import WorkerController

logger = logging.getLogger("alert_engine")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    dsn = (settings.database_url or "").strip()
    if dsn:
        applied_now = ensure_postgres_migrations_applied(dsn)
        try:
            total_mig = count_applied_migrations(dsn)
        except Exception as exc:
            logger.warning("migration count query failed: %s", exc)
            total_mig = -1
        logger.info(
            "alert-engine migrations applied_now=%s schema_migrations_total=%s",
            applied_now,
            total_mig,
        )
    else:
        logger.error("alert-engine DATABASE_URL fehlt — Worker starten nicht")
    wc = WorkerController(settings)
    app.state.worker = wc
    wc.start()
    allowed_env = len(settings.parsed_allowed_chat_ids())
    logger.info(
        "alert-engine workers started telegram_mode=%s dry_run=%s "
        "production=%s allowed_chat_ids_from_env=%s",
        settings.telegram_mode,
        settings.telegram_dry_run,
        settings.production,
        allowed_env,
    )
    yield
    wc.stop()


app = FastAPI(title="alert-engine", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(outbox_router)
app.include_router(admin_router)
app.include_router(webhook_router)
instrument_fastapi(app, "alert-engine")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "alert-engine"}
