"""
Oeffentliche Meta-Schnittstelle: Laufzeit-Kontur ohne Secrets (Evidenz, Monitoring, Dashboard-Chips).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api_gateway.config import get_gateway_settings

router = APIRouter(prefix="/v1/meta", tags=["meta"])


@router.get(
    "/surface",
    summary="Oeffentliche Laufzeit-Kontur",
    description=(
        "Keine Tokens/Keys. Nutzbar fuer Release-Evidenz und Operator-Dashboards. "
        "Siehe scripts/collect_release_evidence.ps1."
    ),
)
def public_runtime_surface() -> dict[str, Any]:
    s = get_gateway_settings()
    return {
        "schema_version": "public-surface-v1",
        "app_env": s.app_env,
        "production": bool(s.production),
        "execution": {
            "execution_mode": str(s.execution_mode),
            "strategy_execution_mode": str(s.strategy_execution_mode),
            "paper_path_active": s.paper_path_active,
            "shadow_trade_enable": bool(s.shadow_trade_enable),
            "live_trade_enable": bool(s.live_trade_enable),
            "live_broker_enabled": bool(s.live_broker_enabled),
        },
        "auth": {
            "sensitive_auth_enforced": s.sensitive_auth_enforced(),
            "gateway_auth_credentials_configured": s.gateway_auth_credentials_configured(),
        },
        "commerce": {
            "commercial_enabled": bool(s.commercial_enabled),
            "payment_checkout_enabled": bool(s.payment_checkout_enabled),
            "payment_environment": s.payment_environment(),
            "telegram_bot_username_configured": bool(s.telegram_bot_username.strip()),
            "telegram_required_for_console": bool(s.commercial_telegram_required_for_console),
        },
        "endpoints": {
            "openapi": "/docs",
            "health": "/health",
            "ready": "/ready",
            "deploy_edge_readiness": "/v1/deploy/edge-readiness",
            "public_surface": "/v1/meta/surface",
        },
        "live_terminal": {
            "sse_enabled": bool(s.live_sse_enabled),
            "sse_ping_sec": int(s.live_sse_ping_sec),
        },
    }
