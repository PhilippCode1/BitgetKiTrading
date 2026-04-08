from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from learning_engine.config import LearningEngineSettings
from learning_engine.registry import models, service
from learning_engine.storage.connection import db_connect
from shared_py.eventbus import RedisStreamBus


def build_registry_router(settings: LearningEngineSettings, bus: RedisStreamBus) -> APIRouter:
    router = APIRouter(prefix="/registry", tags=["registry"])

    def _guard() -> None:
        if not settings.strategy_registry_enabled:
            raise HTTPException(status_code=503, detail="STRATEGY_REGISTRY_ENABLED=false")

    @router.post("/strategies")
    def create_strategy(body: models.CreateStrategyRequest) -> dict[str, Any]:
        _guard()
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                row = service.create_strategy(conn, settings, body)
        return _json_row(row)

    @router.post("/strategies/{strategy_id}/versions")
    def add_version(strategy_id: UUID, body: models.AddVersionRequest) -> dict[str, Any]:
        _guard()
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                vrow = service.add_version(conn, strategy_id, body)
        return _json_row(vrow)

    @router.post("/strategies/{strategy_id}/status")
    def set_status(strategy_id: UUID, body: models.SetStatusRequest) -> dict[str, Any]:
        _guard()
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                out = service.set_status(conn, bus, strategy_id, body)
        return out

    @router.get("/strategies")
    def list_strategies(status: str | None = Query(default=None)) -> dict[str, Any]:
        _guard()
        with db_connect(settings.database_url) as conn:
            rows = service.list_strategies(conn, status)
        return {"status": "ok", "count": len(rows), "items": [_json_row(r) for r in rows]}

    @router.get("/strategies/{strategy_id}")
    def one(strategy_id: UUID) -> dict[str, Any]:
        _guard()
        with db_connect(settings.database_url) as conn:
            detail = service.get_strategy_detail(conn, strategy_id)
        strat = _json_row(detail["strategy"])
        vers = [_json_row(v) for v in detail["versions"]]
        return {"status": "ok", "strategy": strat, "versions": vers}

    return router


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))
