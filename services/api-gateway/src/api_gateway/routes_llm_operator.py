from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.llm_orchestrator_forward import (
    LLMOrchestratorForwardHttpError,
    post_llm_orchestrator_json,
)

logger = logging.getLogger("api_gateway.routes_llm_operator")

router = APIRouter(prefix="/v1/llm/operator", tags=["llm-operator"])


class OperatorExplainGatewayBody(BaseModel):
    question_de: str = Field(..., min_length=3, max_length=8_000)
    readonly_context_json: dict[str, Any] = Field(default_factory=dict)


class AiStrategyProposalDraftGatewayBody(BaseModel):
    chart_context_json: dict[str, Any] = Field(default_factory=dict)
    focus_question_de: str | None = Field(default=None, max_length=8_000)


class StrategySignalExplainGatewayBody(BaseModel):
    signal_context_json: dict[str, Any] = Field(default_factory=dict)
    focus_question_de: str | None = Field(default=None, max_length=8_000)


class SafetyIncidentDiagnosisGatewayBody(BaseModel):
    question_de: str = Field(..., min_length=3, max_length=8_000)
    diagnostic_context_json: dict[str, Any] = Field(default_factory=dict)


@router.post("/explain")
def llm_operator_explain(
    request: Request,
    body: OperatorExplainGatewayBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    """
    Operator-Hilfe: Frage (DE) + optionaler Readonly-Kontext → strukturierte Erklaerung.
    Weiterleitung zum LLM-Orchestrator (interner API-Key, kein OpenAI-Key im Gateway).
    """
    g = get_gateway_settings()
    ctx = body.readonly_context_json or {}
    ctx_keys = list(ctx.keys())[:24]
    record_gateway_audit_line(
        request,
        auth,
        "llm_operator_explain",
        extra={
            "question_len": len(body.question_de),
            "context_key_count": len(ctx),
            "context_top_keys": ctx_keys,
        },
    )
    payload = {
        "question_de": body.question_de,
        "readonly_context_json": body.readonly_context_json,
    }
    try:
        return post_llm_orchestrator_json(
            g,
            "/llm/analyst/operator_explain",
            payload,
            timeout_sec=120.0,
        )
    except RuntimeError as exc:
        logger.warning("llm operator explain config/upstream: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LLM_ORCH_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
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


@router.post("/safety-incident-diagnosis")
def llm_operator_safety_incident_diagnosis(
    request: Request,
    body: SafetyIncidentDiagnosisGatewayBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    """
    Sicherheits-Diagnose: Readonly Health/Alerts-Kontext + Frage → strukturierte Ursachen/Plaene.
    Keine Ausfuehrungshoheit — nur Analyse (Orchestrator, execution_authority none).
    """
    g = get_gateway_settings()
    ctx = body.diagnostic_context_json or {}
    ctx_keys = list(ctx.keys())[:32]
    record_gateway_audit_line(
        request,
        auth,
        "llm_operator_safety_incident_diagnosis",
        extra={
            "question_len": len(body.question_de),
            "context_key_count": len(ctx),
            "context_top_keys": ctx_keys,
        },
    )
    payload = {
        "question_de": body.question_de,
        "diagnostic_context_json": body.diagnostic_context_json,
    }
    try:
        return post_llm_orchestrator_json(
            g,
            "/llm/analyst/safety_incident_diagnosis",
            payload,
            timeout_sec=120.0,
        )
    except RuntimeError as exc:
        logger.warning("llm safety incident diagnosis config/upstream: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LLM_ORCH_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
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


@router.post("/strategy-signal-explain")
def llm_operator_strategy_signal_explain(
    request: Request,
    body: StrategySignalExplainGatewayBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    """
    Strategie-/Signal-Erklaerung: Readonly-Snapshot (JSON) + optionale Fokusfrage → strukturierte Antwort.
    Forward zum LLM-Orchestrator (interner API-Key).
    """
    fq_chk = (body.focus_question_de or "").strip()
    if not body.signal_context_json and len(fq_chk) < 3:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "type": "value_error",
                    "loc": ["body"],
                    "msg": (
                        "signal_context_json must be non-empty or "
                        "focus_question_de at least 3 characters"
                    ),
                }
            ],
        )
    g = get_gateway_settings()
    keys = list(body.signal_context_json.keys())[:32]
    record_gateway_audit_line(
        request,
        auth,
        "llm_operator_strategy_signal_explain",
        extra={
            "signal_context_top_keys": keys,
            "signal_context_key_count": len(body.signal_context_json),
            "has_focus_question": bool((body.focus_question_de or "").strip()),
        },
    )
    fq = (body.focus_question_de or "").strip() or None
    payload = {
        "signal_context_json": body.signal_context_json,
        "focus_question_de": fq,
    }
    try:
        return post_llm_orchestrator_json(
            g,
            "/llm/analyst/strategy_signal_explain",
            payload,
            timeout_sec=120.0,
        )
    except RuntimeError as exc:
        logger.warning("llm strategy signal explain config/upstream: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LLM_ORCH_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
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


@router.post("/ai-strategy-proposal-draft")
def llm_operator_ai_strategy_proposal_draft(
    request: Request,
    body: AiStrategyProposalDraftGatewayBody,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    """
    KI-Strategie-/Szenario-Entwurf (strukturiert, execution_authority none).
    Persistenz: POST /v1/operator/ai-strategy-proposal-drafts/generate-and-store.
    """
    fq_chk = (body.focus_question_de or "").strip()
    if not body.chart_context_json and len(fq_chk) < 3:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "type": "value_error",
                    "loc": ["body"],
                    "msg": (
                        "chart_context_json must be non-empty or "
                        "focus_question_de at least 3 characters"
                    ),
                }
            ],
        )
    g = get_gateway_settings()
    keys = list(body.chart_context_json.keys())[:32]
    record_gateway_audit_line(
        request,
        auth,
        "llm_operator_ai_strategy_proposal_draft",
        extra={
            "chart_context_top_keys": keys,
            "chart_context_key_count": len(body.chart_context_json),
            "has_focus_question": bool((body.focus_question_de or "").strip()),
        },
    )
    fq = (body.focus_question_de or "").strip() or None
    payload = {
        "chart_context_json": body.chart_context_json,
        "focus_question_de": fq,
    }
    try:
        return post_llm_orchestrator_json(
            g,
            "/llm/analyst/ai_strategy_proposal_draft",
            payload,
            timeout_sec=125.0,
        )
    except RuntimeError as exc:
        logger.warning("llm ai strategy proposal draft config/upstream: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LLM_ORCH_UNAVAILABLE",
                "message": str(exc),
            },
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        if exc.status_code in (413, 422):
            raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
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
