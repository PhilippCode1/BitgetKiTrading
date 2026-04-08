from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.analytics.runner import parse_windows
from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_learning_v1
from shared_py.eventbus import RedisStreamBus


def build_learning_health_router(
    settings: LearningEngineSettings, bus: RedisStreamBus | None = None
) -> APIRouter:
    r = APIRouter(tags=["learning"])

    @r.get("/learning/health")
    def learning_health() -> dict[str, Any]:
        db_ok = False
        try:
            with db_connect(settings.database_url) as conn:
                conn.execute("SELECT 1")
                db_ok = True
        except Exception:
            db_ok = False
        redis_ok = False
        try:
            b = bus or RedisStreamBus.from_url(
                settings.redis_url,
                dedupe_ttl_sec=0,
                default_block_ms=settings.eventbus_block_ms,
                default_count=settings.eventbus_count,
            )
            redis_ok = bool(b.ping())
        except Exception:
            redis_ok = False
        try:
            wins = parse_windows(settings)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "status": "ok",
            "service": "learning-engine",
            "db_ok": db_ok,
            "redis_ok": redis_ok,
            "windows": wins,
            "learning_enable_adwin": settings.learning_enable_adwin,
            "learning_enable_mlflow": settings.learning_enable_mlflow,
        }

    @r.get("/learning/metrics/strategies")
    def strategy_metrics_api(window: str = "7d") -> dict[str, Any]:
        w = window.strip().lower()
        try:
            repo_learning_v1.window_to_ms(w)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with db_connect(settings.database_url) as conn:
            rows = repo_learning_v1.list_strategy_metrics(conn, window=w)
        items = [repo_learning_v1.jsonable_row(x) for x in rows]
        return {"status": "ok", "window": w, "count": len(items), "items": items}

    return r


def build_learning_run_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning"])

    @r.post("/learning/run-now")
    def run_now() -> dict[str, Any]:
        from learning_engine.analytics.runner import run_learning_analytics

        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                report = run_learning_analytics(conn, settings)
        payload = json.loads(json.dumps(report, default=str))
        return {"status": "ok", "report": payload}

    return r
