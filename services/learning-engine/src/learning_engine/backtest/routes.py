from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from learning_engine.backtest.runner_offline import run_offline_backtest
from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_backtest
from learning_engine.storage.repo_learning_v1 import jsonable_row


class BacktestRunNowBody(BaseModel):
    from_ts_ms: int = Field(..., description="Inklusiver Start (closed_ts_ms)")
    to_ts_ms: int = Field(..., description="Inklusives Ende")
    cv_method: str | None = Field(
        default=None,
        description="walk_forward | purged_kfold_embargo (Default: ENV)",
    )
    symbol: str = Field(..., description="Explizites Katalogsymbol fuer den Backtest")
    timeframes: list[str] | None = Field(default=None, description='z. B. ["5m"]')
    ephemeral_run: bool = Field(
        default=False,
        description="True: neue run_id (uuid4); False: deterministische run_id (wie CLI-Default)",
    )


def build_backtests_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["backtests"])

    @r.get("/backtests/runs")
    def list_runs(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        with db_connect(settings.database_url) as conn:
            rows = repo_backtest.list_backtest_runs(conn, limit=limit)
        return {
            "status": "ok",
            "count": len(rows),
            "items": [jsonable_row(x) for x in rows],
        }

    @r.get("/backtests/runs/{run_id}")
    def one(run_id: str) -> dict[str, Any]:
        try:
            rid = UUID(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="ungueltige run_id") from exc
        with db_connect(settings.database_url) as conn:
            row = repo_backtest.get_backtest_run(conn, rid)
            if row is None:
                raise HTTPException(status_code=404, detail="run nicht gefunden")
            folds = repo_backtest.list_folds_for_run(conn, rid)
        return {
            "status": "ok",
            "run": jsonable_row(row),
            "folds": [jsonable_row(f) for f in folds],
        }

    @r.post("/backtests/run-now")
    def run_now(body: BacktestRunNowBody) -> dict[str, Any]:
        cv = (body.cv_method or settings.backtest_default_cv).strip().lower()
        if cv not in ("walk_forward", "purged_kfold_embargo"):
            raise HTTPException(status_code=400, detail="cv_method ungueltig")
        span = body.to_ts_ms - body.from_ts_ms
        if span <= 0:
            raise HTTPException(status_code=400, detail="Zeitraum ungueltig")
        max_span = 14 * 24 * 3_600_000
        if span > max_span:
            raise HTTPException(
                status_code=400,
                detail=f"Zeitraum zu gross (max {max_span} ms / ~14d fuer sync run-now)",
            )
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                rid = run_offline_backtest(
                    conn,
                    settings,
                    symbol=body.symbol,
                    from_ts_ms=body.from_ts_ms,
                    to_ts_ms=body.to_ts_ms,
                    cv_method=cv,
                    timeframes=body.timeframes,
                    ephemeral_run=body.ephemeral_run,
                )
        return {
            "status": "ok",
            "run_id": str(rid),
            "cv_method": cv,
            "message": "offline backtest abgeschlossen",
        }

    return r
