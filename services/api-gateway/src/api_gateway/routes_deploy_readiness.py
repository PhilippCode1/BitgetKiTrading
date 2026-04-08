"""
Oeffentliche Deploy-Hilfe: Domain/TLS/Reverse-Proxy — keine Secrets, keine Cloud-Magie.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from api_gateway.config import get_gateway_settings

router = APIRouter(prefix="/v1/deploy", tags=["deploy"])


@router.get("/edge-readiness")
def deploy_edge_readiness(request: Request) -> dict[str, Any]:
    """
    Checkliste fuer Single-Host / Reverse-Proxy-Betrieb.
    Nutzt nur konfigurierte Flags und eingehende Forward-Header — keine Geheimnisse.
    """
    s = get_gateway_settings()
    fwd_proto = (request.headers.get("x-forwarded-proto") or "").strip().lower()
    fwd_host = (request.headers.get("x-forwarded-host") or "").strip()
    origin = (request.headers.get("origin") or "").strip()

    cors = s.cors_allow_origins.strip()
    cors_parts = [p.strip() for p in cors.split(",") if p.strip()]
    if cors_parts:
        cors_https_only = all(o.lower().startswith("https://") for o in cors_parts)
    else:
        cors_https_only = False

    return {
        "app_env": s.app_env,
        "production_profile": bool(s.production),
        "public_endpoints": {
            "health": "/health",
            "ready": "/ready",
            "edge_readiness": "/v1/deploy/edge-readiness",
        },
        "configured_urls": {
            "app_base_url_set": bool(s.app_base_url.strip()),
            "frontend_url_set": bool(s.frontend_url.strip()),
            "cors_origin_count": len(cors_parts),
        },
        "security_headers": {
            "hsts_enabled": bool(s.gateway_send_hsts),
            "content_security_policy_enabled": bool(
                (s.gateway_content_security_policy or "").strip()
            ),
            "sse_cookie_secure": s.sse_cookie_secure_flag(),
            "sse_cookie_samesite": s.gateway_sse_cookie_samesite,
        },
        "cors_https_only": cors_https_only,
        "request_forwarding": {
            "x_forwarded_proto": fwd_proto or None,
            "x_forwarded_host": fwd_host or None,
            "origin_header_seen": bool(origin),
            "hints": [
                "TLS-Terminierung am Reverse-Proxy: X-Forwarded-Proto: https und "
                "X-Forwarded-Host an das API-Gateway durchreichen.",
                "CORS_ALLOW_ORIGINS muss exakt die Browser-Origin des Dashboards "
                "(https://...) enthalten, kommagetrennt.",
                "Bei TLS am Edge: GATEWAY_SEND_HSTS=true und "
                "GATEWAY_SSE_COOKIE_SECURE=true setzen.",
                "Siehe docs/operator_urls_and_secrets.md und "
                "infra/reverse-proxy/README.md.",
            ],
        },
    }
