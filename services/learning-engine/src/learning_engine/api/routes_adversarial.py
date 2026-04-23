from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from learning_engine.config import LearningEngineSettings
from shared_py.service_auth import INTERNAL_SERVICE_HEADER, assert_internal_service_auth


class ToxicBatchProxyBody(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=64)
    seq_len: int = Field(default=128, ge=32, le=2048)
    toxicity_0_1: float = Field(default=0.65, ge=0.0, le=1.0)
    batch: int = Field(default=1, ge=1, le=16)
    anchor_price: float = Field(default=95_000.0, gt=0.0)
    ts_start_ms: int | None = Field(default=None, ge=0)
    step_ms: int = Field(default=250, ge=50, le=60_000)
    seed: int | None = None
    price_depth_rho: float | None = Field(default=None, ge=-0.95, le=0.95)
    return_arrow: bool = Field(default=True)


def build_adversarial_proxy_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "adversarial"])

    @r.post("/learning/adversarial/toxic-batch")
    async def proxy_toxic_batch(
        body: ToxicBatchProxyBody,
        x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
    ) -> dict[str, Any]:
        assert_internal_service_auth(settings, x_internal_service_key)
        base = (settings.adversarial_engine_base_url or "").strip().rstrip("/")
        if not base:
            raise HTTPException(
                status_code=503,
                detail="ADVERSARIAL_ENGINE_BASE_URL nicht gesetzt",
            )
        url = f"{base}/ams/v1/toxic-batch"
        headers: dict[str, str] = {}
        key = str(getattr(settings, "service_internal_api_key", "") or "").strip()
        if key:
            headers[INTERNAL_SERVICE_HEADER] = key
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, json=body.model_dump(), headers=headers)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"adversarial-engine nicht erreichbar: {exc}",
            ) from exc
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text[:2000],
            )
        data = resp.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Ungueltige AMS-Antwort")
        return data

    return r
