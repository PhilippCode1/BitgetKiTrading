from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

_llm_api_log = logging.getLogger("llm_orchestrator.api")

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.requests import Request

from llm_orchestrator.exceptions import LLMPromptTooLargeError
from llm_orchestrator.service import LLMService, ProviderPref
from shared_py.service_auth import (
    InternalServiceAuthContext,
    build_internal_service_dependency,
)

# API-Hardlimit (konfigurierbarer Cap in LLMOrchestratorSettings <= diesem Wert).
_MAX_PROMPT_CHARS_API = 512_000


class StructuredRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_preference: Literal["auto", "openai"] = "auto"
    model: str | None = None
    output_schema: dict[str, Any] = Field(alias="schema_json")
    prompt: str = Field(..., min_length=1, max_length=_MAX_PROMPT_CHARS_API)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    task_type: str | None = Field(
        default=None,
        description="Optional: Audit-Label fuer provenance.task_type (kein Retrieval).",
    )


class NewsSummaryRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    content: str | None = None
    url: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    published_ts_ms: int | None = None
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class AnalystHypothesesRequest(BaseModel):
    context_json: dict[str, Any] = Field(default_factory=dict)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.15, ge=0.0, le=2.0)


class AnalystContextClassificationRequest(BaseModel):
    narrative_de: str = Field(..., min_length=3, max_length=48_000)
    instrument_hint: str | None = Field(default=None, max_length=512)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.15, ge=0.0, le=2.0)


class PostTradeReviewRequest(BaseModel):
    trade_facts_json: dict[str, Any] = Field(default_factory=dict)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class OperatorExplainRequest(BaseModel):
    question_de: str = Field(..., min_length=3, max_length=8_000)
    readonly_context_json: dict[str, Any] = Field(default_factory=dict)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class SafetyIncidentDiagnosisRequest(BaseModel):
    question_de: str = Field(..., min_length=3, max_length=8_000)
    diagnostic_context_json: dict[str, Any] = Field(default_factory=dict)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class StrategySignalExplainRequest(BaseModel):
    signal_context_json: dict[str, Any] = Field(default_factory=dict)
    focus_question_de: str | None = Field(default=None, max_length=8_000)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class AiStrategyProposalDraftRequest(BaseModel):
    chart_context_json: dict[str, Any] = Field(default_factory=dict)
    focus_question_de: str | None = Field(default=None, max_length=8_000)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class StrategyJournalSummaryRequest(BaseModel):
    journal_events_json: list[Any] | dict[str, Any]
    period_label_de: str | None = Field(default=None, max_length=256)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class AssistTurnRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assist_role: Literal[
        "admin_operations",
        "strategy_signal",
        "customer_onboarding",
        "support_billing",
    ]
    conversation_id: str = Field(..., min_length=36, max_length=36)
    tenant_partition_id: str = Field(..., min_length=1, max_length=256)
    user_message_de: str = Field(..., min_length=3, max_length=8_000)
    context_json: dict[str, Any] = Field(default_factory=dict)
    provider_preference: ProviderPref = "auto"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    @field_validator("conversation_id")
    @classmethod
    def _conversation_uuid(cls, v: str) -> str:
        UUID(v)
        return v


def build_router(service: LLMService, *, settings: Any) -> APIRouter:
    r = APIRouter()
    require_internal = build_internal_service_dependency(settings)

    def _llm_http_error(exc: LLMPromptTooLargeError | RuntimeError) -> HTTPException:
        if isinstance(exc, LLMPromptTooLargeError):
            return HTTPException(
                status_code=413,
                detail={"code": "PROMPT_TOO_LARGE", "message": str(exc)},
            )
        hint = service.peek_last_structured_failure()
        detail: dict[str, Any] = {"code": "LLM_UNAVAILABLE", "message": str(exc)}
        if hint and hint.get("failure_class"):
            detail["failure_class"] = hint["failure_class"]
        return HTTPException(status_code=502, detail=detail)

    @r.get("/health")
    def health(request: Request) -> dict[str, Any]:
        rid = (request.headers.get("x-request-id") or "").strip()
        if rid:
            _llm_api_log.debug("health probe request_id=%s", rid)
        return service.health()

    @r.get("/llm/governance/summary")
    def llm_governance_summary(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        return service.governance_summary()

    @r.post("/llm/structured")
    def llm_structured(
        structured: StructuredRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_structured(
                schema_json=structured.output_schema,
                prompt=structured.prompt,
                temperature=structured.temperature,
                provider_preference=structured.provider_preference,
                model=structured.model,
                task_type=structured.task_type,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/news_summary")
    def llm_news_summary(
        news: NewsSummaryRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_news_summary(
                title=news.title,
                description=news.description,
                content=news.content,
                url=news.url,
                source=news.source,
                published_ts_ms=news.published_ts_ms,
                provider_preference=news.provider_preference,
                model=news.model,
                temperature=news.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/hypotheses")
    def llm_analyst_hypotheses(
        body: AnalystHypothesesRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_analyst_hypotheses(
                context_json=body.context_json,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/context_classification")
    def llm_analyst_context_classification(
        body: AnalystContextClassificationRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_analyst_context_classification(
                narrative_de=body.narrative_de,
                instrument_hint=body.instrument_hint,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/post_trade_review")
    def llm_analyst_post_trade_review(
        body: PostTradeReviewRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_post_trade_review(
                trade_facts_json=body.trade_facts_json,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/operator_explain")
    def llm_analyst_operator_explain(
        body: OperatorExplainRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_operator_explain(
                question_de=body.question_de,
                readonly_context_json=body.readonly_context_json,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/safety_incident_diagnosis")
    def llm_analyst_safety_incident_diagnosis(
        body: SafetyIncidentDiagnosisRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_safety_incident_diagnosis(
                question_de=body.question_de,
                diagnostic_context_json=body.diagnostic_context_json,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/strategy_signal_explain")
    def llm_analyst_strategy_signal_explain(
        body: StrategySignalExplainRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
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
        try:
            return service.run_strategy_signal_explain(
                signal_context_json=body.signal_context_json,
                focus_question_de=body.focus_question_de,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/ai_strategy_proposal_draft")
    def llm_analyst_ai_strategy_proposal_draft(
        body: AiStrategyProposalDraftRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
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
        try:
            return service.run_ai_strategy_proposal_draft(
                chart_context_json=body.chart_context_json,
                focus_question_de=body.focus_question_de,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/analyst/strategy_journal_summary")
    def llm_analyst_strategy_journal_summary(
        body: StrategyJournalSummaryRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_strategy_journal_summary(
                journal_events_json=body.journal_events_json,
                period_label_de=body.period_label_de,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    @r.post("/llm/assist/turn")
    def llm_assist_turn(
        body: AssistTurnRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            return service.run_assistant_turn(
                assist_role=body.assist_role,
                conversation_id=body.conversation_id,
                tenant_partition_id=body.tenant_partition_id,
                user_message_de=body.user_message_de,
                context_json=body.context_json,
                provider_preference=body.provider_preference,
                model=body.model,
                temperature=body.temperature,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "ASSIST_ROLE_INVALID", "message": str(exc)},
            ) from exc
        except (LLMPromptTooLargeError, RuntimeError) as exc:
            raise _llm_http_error(exc) from exc

    return r
