from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_learning_v1


def build_recommendations_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning"])

    @r.get("/learning/recommendations/recent")
    def recent(limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit 1..200")
        with db_connect(settings.database_url) as conn:
            rows = repo_learning_v1.list_recent_recommendations(conn, limit=limit)
        items = [repo_learning_v1.jsonable_row(x) for x in rows]
        return {"status": "ok", "count": len(items), "items": items}

    return r
