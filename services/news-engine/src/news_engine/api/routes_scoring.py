from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from news_engine.scoring.runner import run_scoring_batch


def build_scoring_router(runtime: Any) -> APIRouter:
    r = APIRouter()

    @r.post("/score/now")
    async def score_now() -> dict[str, object]:
        out = await asyncio.to_thread(
            run_scoring_batch, runtime.settings, runtime.repo, runtime.bus
        )
        return {"status": "ok", **out}

    @r.get("/news/scored")
    def news_scored(min_score: int = 0, limit: int = 20) -> dict[str, object]:
        lo = min(max(min_score, 0), 100)
        lim = min(max(limit, 1), 100)
        rows = runtime.repo.list_scored(min_score=lo, limit=lim)
        return {"status": "ok", "items": rows}

    @r.get("/news/{row_id}")
    def news_by_id(row_id: int) -> dict[str, object]:
        row = runtime.repo.get_by_id(row_id)
        if row is None:
            raise HTTPException(status_code=404, detail="news item not found")
        return {"status": "ok", "item": row}

    return r
