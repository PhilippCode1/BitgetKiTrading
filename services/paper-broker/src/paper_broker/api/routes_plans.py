from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from paper_broker.engine.broker import PaperBrokerService


class PlanAutoBody(BaseModel):
    timeframe: str = Field(..., description="z.B. 1m, 5m, 15m, 1h, 4h")
    preferred_trigger_type: str | None = Field(
        default=None, description="mark_price oder fill_price (Stop)"
    )
    method_mix: dict[str, bool] | None = Field(
        default=None,
        description="Optional: volatility, invalidation, liquidity",
    )


class PlanOverrideBody(BaseModel):
    stop_plan: dict[str, Any] | None = None
    tp_plan: dict[str, Any] | None = None


def build_plans_router(broker: PaperBrokerService) -> APIRouter:
    r = APIRouter(prefix="/paper")

    @r.post("/positions/{position_id}/plan/auto")
    def plan_auto(position_id: str, body: PlanAutoBody) -> dict[str, Any]:
        try:
            out = broker.plan_auto(
                UUID(position_id),
                timeframe=body.timeframe,
                preferred_trigger_type=body.preferred_trigger_type,
                method_mix=body.method_mix,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **out}

    @r.get("/positions/{position_id}/plan")
    def plan_get(position_id: str) -> dict[str, Any]:
        try:
            return {"status": "ok", **broker.get_position_plan(UUID(position_id))}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @r.post("/positions/{position_id}/plan/override")
    def plan_override(position_id: str, body: PlanOverrideBody) -> dict[str, Any]:
        try:
            out = broker.plan_override(
                UUID(position_id),
                stop_patch=body.stop_plan,
                tp_patch=body.tp_plan,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **out}

    return r
