from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from paper_broker.engine.broker import PaperBrokerService, SimFundingState, SimMarketState


class SimMarketBody(BaseModel):
    ts_ms: int
    best_bid: str
    best_ask: str
    last_price: str
    mark_price: str


class SimFundingBody(BaseModel):
    funding_rate: str
    funding_interval_hours: int = 8
    next_update_ms: int


def build_sim_router(broker: PaperBrokerService) -> APIRouter:
    r = APIRouter(prefix="/paper/sim")

    @r.post("/market")
    def sim_market(body: SimMarketBody) -> dict[str, Any]:
        broker.set_sim_market(
            SimMarketState(
                ts_ms=body.ts_ms,
                best_bid=Decimal(body.best_bid),
                best_ask=Decimal(body.best_ask),
                last_price=Decimal(body.last_price),
                mark_price=Decimal(body.mark_price),
            )
        )
        return {"status": "ok"}

    @r.post("/funding")
    def sim_funding(body: SimFundingBody) -> dict[str, Any]:
        broker.set_sim_funding(
            SimFundingState(
                funding_rate=Decimal(body.funding_rate),
                funding_interval_hours=body.funding_interval_hours,
                next_update_ms=body.next_update_ms,
            )
        )
        return {"status": "ok"}

    return r
