from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from learning_engine.config import LearningEngineSettings
from learning_engine.drift.online_evaluator import run_online_drift_evaluation
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_online_drift
from shared_py.learning_drift_api import (
    drift_recent_response,
    learning_engine_online_drift_state_body,
)


def build_online_drift_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "online-drift"])

    @r.get("/learning/drift/online-state", response_model=None)
    def online_state() -> dict[str, Any]:
        with db_connect(settings.database_url) as conn:
            row = repo_online_drift.fetch_online_drift_state(conn, scope="global")
        return learning_engine_online_drift_state_body(row)

    @r.get("/learning/drift/recent", response_model=None)
    def drift_recent(limit: int = 50) -> dict[str, Any]:
        lim = max(1, min(int(limit), 500))
        with db_connect(settings.database_url) as conn:
            items = repo_online_drift.fetch_drift_events_recent(conn, limit=lim)
        return drift_recent_response(items=items, limit=lim)

    @r.post("/learning/drift/evaluate-now", response_model=None)
    def evaluate_now() -> dict[str, Any]:
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                out = run_online_drift_evaluation(conn, settings)
        return {"status": "ok", **out}

    return r
