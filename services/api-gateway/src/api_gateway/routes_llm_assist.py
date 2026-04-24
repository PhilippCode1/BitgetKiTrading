from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from shared_py.llm_assist_context import filter_assist_context_payload

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import (
    GatewayAuthContext,
    require_admin_read,
    require_billing_read,
)
from api_gateway.config import get_gateway_settings
from api_gateway.deps import require_commercial_entitlement
from api_gateway.llm_orchestrator_forward import (
    LLMOrchestratorForwardHttpError,
    post_llm_orchestrator_json,
)

logger = logging.getLogger("api_gateway.routes_llm_assist")

router = APIRouter(prefix="/v1/llm/assist", tags=["llm-assist"])


class AssistTurnPublicBody(BaseModel):
    conversation_id: str = Field(..., min_length=36, max_length=36)
    user_message_de: str = Field(..., min_length=3, max_length=8_000)
    context_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("conversation_id")
    @classmethod
    def _cv(cls, v: str) -> str:
        UUID(v)
        return v


def _partition_admin(ctx: GatewayAuthContext) -> str:
    raw = f"assist|admin|{ctx.actor}|{ctx.auth_method}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _partition_strategy(ctx: GatewayAuthContext) -> str:
    raw = f"assist|strat|{ctx.actor}|{ctx.auth_method}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _partition_customer(ctx: GatewayAuthContext, default_tid: str) -> str:
    tid = ctx.effective_tenant(default_tenant_id=default_tid).strip()
    if not tid:
        tid = default_tid
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in tid)[:200]
    return safe or "tenant"


def _forward_turn(
    *,
    request: Request,
    auth: GatewayAuthContext,
    assist_role: str,
    tenant_partition_id: str,
    body: AssistTurnPublicBody,
    audit_action: str,
) -> dict[str, Any]:
    try:
        filtered = filter_assist_context_payload(assist_role, body.context_json)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "ASSIST_CONTEXT_INVALID", "message": str(exc)},
        ) from exc
    g = get_gateway_settings()
    record_gateway_audit_line(
        request,
        auth,
        audit_action,
        extra={
            "assist_role": assist_role,
            "conversation_id": body.conversation_id,
            "context_key_count": len(filtered),
            "msg_len": len(body.user_message_de),
        },
    )
    payload = {
        "assist_role": assist_role,
        "conversation_id": body.conversation_id,
        "tenant_partition_id": tenant_partition_id,
        "user_message_de": body.user_message_de.strip(),
        "context_json": filtered,
    }
    try:
        return post_llm_orchestrator_json(
            g,
            "/llm/assist/turn",
            payload,
            timeout_sec=120.0,
        )
    except RuntimeError as exc:
        logger.warning("llm assist turn config/upstream: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_ORCH_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.payload,
            ) from exc
        if exc.status_code == 502:
            raise HTTPException(
                status_code=502,
                detail=exc.payload
                if isinstance(exc.payload, dict)
                else {"message": str(exc.payload)},
            ) from exc
        raise HTTPException(
            status_code=502,
            detail={
                "code": "LLM_ORCH_ERROR",
                "upstream_status": exc.status_code,
                "message": exc.payload,
            },
        ) from exc


@router.post("/ops-risk/turn")
def llm_assist_ops_risk_turn(
    request: Request,
    body: AssistTurnPublicBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    return _forward_turn(
        request=request,
        auth=auth,
        assist_role="ops_risk",
        tenant_partition_id=_partition_admin(auth),
        body=body,
        audit_action="llm_assist_ops_risk_turn",
    )


@router.post("/admin-operations/turn")
def llm_assist_admin_operations_turn(
    request: Request,
    body: AssistTurnPublicBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    return _forward_turn(
        request=request,
        auth=auth,
        assist_role="admin_operations",
        tenant_partition_id=_partition_admin(auth),
        body=body,
        audit_action="llm_assist_admin_operations_turn",
    )


@router.post("/strategy-signal/turn")
def llm_assist_strategy_signal_turn(
    request: Request,
    body: AssistTurnPublicBody,
    auth: Annotated[GatewayAuthContext, Depends(require_commercial_entitlement("AI_DEEP_ANALYSIS"))],
) -> dict[str, Any]:
    return _forward_turn(
        request=request,
        auth=auth,
        assist_role="strategy_signal",
        tenant_partition_id=_partition_strategy(auth),
        body=body,
        audit_action="llm_assist_strategy_signal_turn",
    )


@router.post("/customer-onboarding/turn")
def llm_assist_customer_onboarding_turn(
    request: Request,
    body: AssistTurnPublicBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    g = get_gateway_settings()
    default_tid = g.commercial_default_tenant_id.strip() or "default"
    return _forward_turn(
        request=request,
        auth=auth,
        assist_role="customer_onboarding",
        tenant_partition_id=_partition_customer(auth, default_tid),
        body=body,
        audit_action="llm_assist_customer_onboarding_turn",
    )


@router.post("/support-billing/turn")
def llm_assist_support_billing_turn(
    request: Request,
    body: AssistTurnPublicBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    g = get_gateway_settings()
    default_tid = g.commercial_default_tenant_id.strip() or "default"
    return _forward_turn(
        request=request,
        auth=auth,
        assist_role="support_billing",
        tenant_partition_id=_partition_customer(auth, default_tid),
        body=body,
        audit_action="llm_assist_support_billing_turn",
    )
