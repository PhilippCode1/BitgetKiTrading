"""Operator: KI-Strategie-Entwuerfe persistieren, validieren, Promotion protokollieren (keine Orders)."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api_gateway.ai_strategy_proposal_governance import (
    assert_promotion_allowed,
    normalize_proposal_payload,
    run_deterministic_validation,
)
from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db_ai_strategy_proposal_drafts import (
    connect_drafts,
    fetch_draft,
    insert_proposal_draft,
    list_drafts_for_signal,
    update_promotion_request,
    update_validation,
)
from api_gateway.llm_orchestrator_forward import (
    LLMOrchestratorForwardHttpError,
    post_llm_orchestrator_json,
)

logger = logging.getLogger("api_gateway.routes_ai_strategy_proposal_drafts")

router = APIRouter(
    prefix="/v1/operator/ai-strategy-proposal-drafts",
    tags=["operator-ai-strategy-drafts"],
)

_CONTEXT_MAX_CHARS = 96_000


class GenerateAndStoreBody(BaseModel):
    chart_context_json: dict[str, Any] = Field(default_factory=dict)
    focus_question_de: str | None = Field(default=None, max_length=8_000)
    signal_id: str | None = Field(default=None, max_length=128)
    symbol: str = Field(default="", max_length=64)
    timeframe: str = Field(default="", max_length=32)


class PromotionRequestBody(BaseModel):
    human_acknowledged: bool = False
    promotion_target: Literal[
        "paper_sandbox", "shadow_observe", "live_requires_full_gates"
    ]


def _require_chart_or_focus(body: GenerateAndStoreBody) -> None:
    fq = (body.focus_question_de or "").strip()
    if not body.chart_context_json and len(fq) < 3:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CHART_CONTEXT_OR_FOCUS_REQUIRED",
                "message": (
                    "chart_context_json must be non-empty or "
                    "focus_question_de at least 3 characters"
                ),
            },
        )


@router.post("/generate-and-store")
def ai_strategy_proposal_generate_and_store(
    request: Request,
    body: GenerateAndStoreBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    _require_chart_or_focus(body)
    try:
        raw = json.dumps(body.chart_context_json)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "CONTEXT_NOT_SERIALIZABLE", "message": str(exc)},
        ) from exc
    if len(raw) > _CONTEXT_MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "CHART_CONTEXT_TOO_LARGE",
                "message": f"chart_context_json exceeds {_CONTEXT_MAX_CHARS} characters.",
            },
        )

    g = get_gateway_settings()
    fq = (body.focus_question_de or "").strip() or None
    record_gateway_audit_line(
        request,
        auth,
        "ai_strategy_proposal_generate_store",
        extra={
            "signal_id": body.signal_id,
            "chart_context_keys": list(body.chart_context_json.keys())[:24],
            "has_focus": bool(fq),
        },
    )
    payload = {
        "chart_context_json": body.chart_context_json,
        "focus_question_de": fq,
    }
    try:
        llm_out = post_llm_orchestrator_json(
            g,
            "/llm/analyst/ai_strategy_proposal_draft",
            payload,
            timeout_sec=125.0,
        )
    except RuntimeError as exc:
        logger.warning("ai strategy proposal orch unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_ORCH_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
        raise HTTPException(
            status_code=502,
            detail={
                "code": "LLM_ORCH_ERROR",
                "upstream_status": exc.status_code,
                "message": exc.payload,
            },
        ) from exc

    if llm_out.get("ok") is False:
        raise HTTPException(
            status_code=502,
            detail={"code": "LLM_RESULT_NOT_OK", "message": llm_out},
        )

    result = llm_out.get("result")
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "LLM_RESULT_MISSING", "message": "Orchestrator returned no result dict."},
        )
    normalized = normalize_proposal_payload(result)

    try:
        with connect_drafts() as conn:
            draft_id = insert_proposal_draft(
                conn,
                operator_actor=auth.actor,
                signal_id=body.signal_id,
                symbol=body.symbol or "",
                timeframe=body.timeframe or "",
                proposal_payload=normalized,
            )
            conn.commit()
    except psycopg.errors.UndefinedTable as exc:
        logger.warning("ai_strategy_proposal_draft table missing: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_STRATEGY_PROPOSAL_TABLE_MISSING",
                "message": "Run postgres migration 615_ai_strategy_proposal_draft.sql.",
            },
        ) from exc
    except psycopg.Error as exc:
        logger.warning("ai_strategy_proposal_draft insert failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_DB_ERROR", "message": str(exc)},
        ) from exc

    return {
        "ok": True,
        "draft_id": str(draft_id),
        "lifecycle_status": "draft",
        "provider": llm_out.get("provider"),
        "model": llm_out.get("model"),
        "result": normalized,
        "provenance": llm_out.get("provenance"),
    }


@router.get("")
def list_ai_strategy_proposal_drafts(
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
    signal_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    del auth
    try:
        with connect_drafts() as conn:
            rows = list_drafts_for_signal(conn, signal_id=signal_id, limit=limit)
    except psycopg.errors.UndefinedTable:
        return {"ok": True, "items": [], "degraded": True, "reason": "table_missing"}
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_DB_ERROR", "message": str(exc)},
        ) from exc
    return {"ok": True, "items": rows}


@router.get("/{draft_id}")
def get_ai_strategy_proposal_draft(
    draft_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    del auth
    try:
        with connect_drafts() as conn:
            row = fetch_draft(conn, draft_id)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_TABLE_MISSING", "message": "Migration pending."},
        )
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_DB_ERROR", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return {"ok": True, "draft": dict(row)}


@router.post("/{draft_id}/validate-deterministic")
def validate_ai_strategy_proposal_draft(
    request: Request,
    draft_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    record_gateway_audit_line(
        request,
        auth,
        "ai_strategy_proposal_validate",
        extra={"draft_id": str(draft_id)},
    )
    try:
        with connect_drafts() as conn:
            row = fetch_draft(conn, draft_id)
            if row is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
            payload = row.get("proposal_payload_jsonb")
            if not isinstance(payload, dict):
                payload = dict(payload or {})
            ok, report = run_deterministic_validation(payload)
            update_validation(conn, draft_id=draft_id, passed=ok, report=report)
            conn.commit()
    except HTTPException:
        raise
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_TABLE_MISSING", "message": "Migration pending."},
        )
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_DB_ERROR", "message": str(exc)},
        ) from exc
    return {"ok": True, "draft_id": str(draft_id), "validation": report}


@router.post("/{draft_id}/request-promotion")
def request_promotion_ai_strategy_proposal_draft(
    request: Request,
    draft_id: UUID,
    body: PromotionRequestBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    record_gateway_audit_line(
        request,
        auth,
        "ai_strategy_proposal_request_promotion",
        extra={
            "draft_id": str(draft_id),
            "target": body.promotion_target,
            "human_ack": body.human_acknowledged,
        },
    )
    try:
        with connect_drafts() as conn:
            row = fetch_draft(conn, draft_id)
            if row is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
            assert_promotion_allowed(
                lifecycle_status=str(row["lifecycle_status"]),
                human_acknowledged=body.human_acknowledged,
                promotion_target=body.promotion_target,
            )
            update_promotion_request(
                conn,
                draft_id=draft_id,
                promotion_target=body.promotion_target,
            )
            conn.commit()
    except HTTPException:
        raise
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_TABLE_MISSING", "message": "Migration pending."},
        )
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "AI_STRATEGY_PROPOSAL_DB_ERROR", "message": str(exc)},
        ) from exc

    return {
        "ok": True,
        "draft_id": str(draft_id),
        "lifecycle_status": "promotion_requested",
        "promotion_target_requested": body.promotion_target,
        "note_de": (
            "Nur Protokoll — keine Order, kein Paper-Broker-Trigger. "
            "Umsetzung über bestehende Produkt-Freigaben und Runbooks."
        ),
    }
