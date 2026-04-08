from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from paper_broker.engine.broker import PaperBrokerService


class OpenPositionBody(BaseModel):
    account_id: str
    symbol: str
    side: str = Field(..., description="long oder short")
    qty_base: str
    leverage: str | None = None
    margin_mode: str | None = None
    order_type: str = "market"


class ClosePositionBody(BaseModel):
    qty_base: str
    order_type: str = "market"


class ProcessTickBody(BaseModel):
    now_ms: int


def build_positions_router(broker: PaperBrokerService, settings: Any) -> APIRouter:
    r = APIRouter(prefix="/paper")

    @r.post("/positions/open")
    def open_pos(body: OpenPositionBody) -> dict[str, Any]:
        lev = Decimal(body.leverage or settings.paper_default_leverage)
        mm = (body.margin_mode or settings.paper_default_margin_mode).lower()
        try:
            out = broker.open_position(
                account_id=UUID(body.account_id),
                symbol=body.symbol,
                side=body.side,
                qty_base=Decimal(body.qty_base),
                leverage=lev,
                margin_mode=mm,
                order_type=body.order_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **out}

    @r.post("/positions/{position_id}/close")
    def close_pos(position_id: str, body: ClosePositionBody) -> dict[str, Any]:
        try:
            out = broker.close_position(
                UUID(position_id),
                qty_base=Decimal(body.qty_base),
                order_type=body.order_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **out}

    @r.post("/process_tick")
    def process_tick(body: ProcessTickBody) -> dict[str, Any]:
        return {"status": "ok", **broker.process_tick(body.now_ms)}

    return r
