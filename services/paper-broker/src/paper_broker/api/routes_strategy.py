from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from paper_broker.config import PaperBrokerSettings
from paper_broker.storage.connection import paper_connect
from paper_broker.storage import repo_strategy
from paper_broker.strategy.engine import StrategyExecutionEngine


class SymbolBody(BaseModel):
    symbol: str = Field(..., description="Explizites Symbol, keine implizite Produktionsvorgabe")


def _serialize_position(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))


def build_strategy_router(
    settings: PaperBrokerSettings, engine: StrategyExecutionEngine
) -> APIRouter:
    r = APIRouter(tags=["strategy"])

    @r.get("/strategy/status")
    def strat_status(symbol: str) -> dict[str, Any]:
        return {"status": "ok", **engine.strategy_status(symbol)}

    @r.post("/strategy/pause")
    def strat_pause(body: SymbolBody) -> dict[str, Any]:
        engine.strategy_pause(body.symbol)
        return {"status": "ok", "symbol": body.symbol.upper(), "paused": True}

    @r.post("/strategy/resume")
    def strat_resume(body: SymbolBody) -> dict[str, Any]:
        engine.strategy_resume(body.symbol)
        return {"status": "ok", "symbol": body.symbol.upper(), "paused": False}

    @r.get("/strategy/rules")
    def strat_rules() -> dict[str, Any]:
        return {"status": "ok", "rules": engine.strategy_rules()}

    @r.get("/paper/trades/recent")
    def trades_recent(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        with paper_connect(settings.database_url, autocommit=True) as conn:
            rows = repo_strategy.list_recent_positions(conn, limit=limit)
        return {"status": "ok", "count": len(rows), "positions": [_serialize_position(x) for x in rows]}

    return r
