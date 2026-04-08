from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from paper_broker.engine.broker import PaperBrokerService


class BootstrapBody(BaseModel):
    initial_equity_usdt: str | None = Field(
        default=None,
        description="Optional; sonst PAPER_ACCOUNT_INITIAL_EQUITY_USDT",
    )


def build_accounts_router(broker: PaperBrokerService, settings: Any) -> APIRouter:
    r = APIRouter(prefix="/paper")

    @r.post("/accounts/bootstrap")
    def bootstrap(body: BootstrapBody) -> dict[str, Any]:
        raw = body.initial_equity_usdt or settings.paper_account_initial_equity_usdt
        aid = broker.bootstrap_account(Decimal(str(raw)))
        return {"status": "ok", "account_id": str(aid)}

    return r
