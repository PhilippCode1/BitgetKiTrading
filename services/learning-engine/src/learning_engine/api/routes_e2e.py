from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_e2e


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))


def build_e2e_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter()

    @r.get("/learning/e2e/recent")
    def recent(limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit 1..200")
        with db_connect(settings.database_url) as conn:
            rows = repo_e2e.list_recent_e2e(conn, limit=limit)
        return {"status": "ok", "schema": "learn.e2e_decision_records", "count": len(rows), "items": [_jsonable(x) for x in rows]}

    return r
