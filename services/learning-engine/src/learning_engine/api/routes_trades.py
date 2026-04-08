from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_eval


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))


def build_trades_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter()

    @r.get("/learning/trades/recent")
    def recent(limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit 1..200")
        with db_connect(settings.database_url) as conn:
            rows = repo_eval.list_recent_evaluations(conn, limit=limit)
        return {"status": "ok", "count": len(rows), "items": [_jsonable(x) for x in rows]}

    @r.get("/learning/trades/{paper_trade_id}")
    def one(paper_trade_id: str) -> dict[str, Any]:
        try:
            pid = UUID(paper_trade_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid uuid") from exc
        with db_connect(settings.database_url) as conn:
            row = repo_eval.get_evaluation_by_trade_id(conn, pid)
        if row is None:
            raise HTTPException(status_code=404, detail="not found")
        return {"status": "ok", "evaluation": _jsonable(row)}

    return r
