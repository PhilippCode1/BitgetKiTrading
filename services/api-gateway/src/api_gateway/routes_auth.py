from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.manual_action import (
    EMERGENCY_ROUTE_KEYS,
    OPERATOR_ROUTE_KEYS,
    ROUTE_KEY_OPERATOR_RELEASE,
    mint_manual_action_token,
)
from api_gateway.mutation_deps import _resolve_live_broker_mutation_context_impl
from api_gateway.sse_ticket import build_sse_ticket, resolve_sse_signing_secret

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_ALLOWED_MINT_ROUTE_KEYS: frozenset[str] = OPERATOR_ROUTE_KEYS | EMERGENCY_ROUTE_KEYS


class ManualActionMintRequest(BaseModel):
    route_key: str = Field(min_length=8, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/sse-cookie")
def issue_sse_session_cookie(
    request: Request,
    response: Response,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, bool]:
    """Stellt ein kurzlebiges HttpOnly-Cookie aus — fuer Browser-EventSource ohne Authorization-Header."""
    settings = get_gateway_settings()
    secret = resolve_sse_signing_secret(settings)
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SSE_COOKIE_UNAVAILABLE",
                "message": "SSE-Signing-Secret nicht konfiguriert.",
            },
        )
    ttl = int(settings.gateway_sse_cookie_ttl_sec)
    ticket = build_sse_ticket(secret=secret, sub=auth.actor, ttl_sec=ttl)
    response.set_cookie(
        key=settings.gateway_sse_cookie_name,
        value=ticket,
        max_age=ttl,
        httponly=True,
        secure=settings.sse_cookie_secure_flag(),
        samesite=settings.gateway_sse_cookie_samesite,
        path="/",
    )
    record_gateway_audit_line(
        request,
        auth,
        "sse_session_cookie_issued",
        extra={"ttl_sec": ttl},
    )
    return {"ok": True}


@router.post("/manual-action/mint")
def mint_manual_action_route(
    request: Request,
    body: ManualActionMintRequest,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias="X-Gateway-Internal-Key"),
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """
    Kurzlebiger Token fuer POST /v1/live-broker/safety/* und operator-release.
    Payload muss byte-identisch zur spaeteren Mutation sein (inkl. Sortierung der Keys im Fingerprint).
    operator_release: payload enthaelt `_execution_id` (UUID-String) plus optionale audit-Felder.
    """
    rk = body.route_key.strip()
    if rk not in _ALLOWED_MINT_ROUTE_KEYS:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNKNOWN_ROUTE_KEY", "message": "route_key nicht erlaubt."},
        )
    if rk == ROUTE_KEY_OPERATOR_RELEASE:
        eid = body.payload.get("_execution_id")
        if not eid or not str(eid).strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "EXECUTION_ID_REQUIRED",
                    "message": "payload._execution_id fuer operator_release erforderlich.",
                },
            )
    auth = _resolve_live_broker_mutation_context_impl(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=x_admin_token,
        route_key=rk,
    )
    settings = get_gateway_settings()
    token, exp = mint_manual_action_token(
        settings=settings,
        actor=auth.actor,
        route_key=rk,
        payload=body.payload,
    )
    record_gateway_audit_line(
        request,
        auth,
        "manual_action_token_minted",
        extra={"route_key": rk, "expires_at": exp},
    )
    return {"token": token, "expires_at": exp, "route_key": rk}
