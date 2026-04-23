from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter

from api_gateway.config import get_gateway_settings
from config.internal_service_discovery import http_base_from_health_or_ready_url

logger = logging.getLogger("api_gateway.correlation_proxy")

router = APIRouter(prefix="/v1/correlation", tags=["correlation"])


@router.get("/matrix", response_model=None)
async def correlation_matrix() -> dict[str, Any]:
    """Proxy zur feature-engine: Apex-Korrelationsmatrix (TradFi vs Krypto)."""
    settings = get_gateway_settings()
    base = http_base_from_health_or_ready_url(settings.health_url_feature_engine)
    if not base:
        return {
            "status": "degraded",
            "message": "HEALTH_URL_FEATURE_ENGINE nicht gesetzt — keine feature-engine Basis-URL.",
            "correlation": None,
        }
    url = f"{base}/correlation/matrix"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(url)
    except httpx.RequestError as exc:
        logger.warning("correlation matrix proxy: %s", exc)
        return {
            "status": "degraded",
            "message": f"feature-engine nicht erreichbar: {exc}",
            "correlation": None,
        }
    try:
        data = r.json()
    except Exception as exc:
        return {
            "status": "degraded",
            "message": f"Ungueltige JSON-Antwort: {exc}",
            "correlation": None,
        }
    if not isinstance(data, dict):
        return {"status": "degraded", "message": "Leere oder ungueltige Antwort.", "correlation": None}
    return data
