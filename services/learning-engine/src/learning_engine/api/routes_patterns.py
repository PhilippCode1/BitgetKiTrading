from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.analytics import error_patterns
from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_learning_v1


def build_patterns_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning"])

    @r.get("/learning/patterns/top")
    def top_patterns(window: str = "7d", limit: int = 20) -> dict[str, Any]:
        w = window.strip().lower()
        try:
            wms = repo_learning_v1.window_to_ms(w)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        now_ms = int(time.time() * 1000)
        since = now_ms - wms
        with db_connect(settings.database_url) as conn:
            stored = repo_learning_v1.list_error_patterns_top(conn, window=w, limit=limit)
            rows = repo_learning_v1.fetch_evaluations_since_ms(conn, since_closed_ts_ms=since)
        losing = error_patterns.top_losing_conditions(rows, limit=10)
        return {
            "status": "ok",
            "window": w,
            "patterns": [repo_learning_v1.jsonable_row(dict(x)) for x in stored],
            "losing_conditions": json.loads(json.dumps(losing, default=str)),
        }

    return r
