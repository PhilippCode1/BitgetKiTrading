from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_eval


def build_summary_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter()

    @r.get("/learning/summary")
    def summary(window_days: int = 7) -> dict[str, Any]:
        if window_days < 1 or window_days > 365:
            raise HTTPException(status_code=400, detail="window_days 1..365")
        with db_connect(settings.database_url) as conn:
            s = repo_eval.summary_window(conn, window_days=window_days)
        payload = json.loads(json.dumps(s, default=str))
        return {"status": "ok", "window_days": window_days, **payload}

    return r
