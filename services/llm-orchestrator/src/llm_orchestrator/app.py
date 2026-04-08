from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from llm_orchestrator.api.routes import build_router
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.constants import LLM_ORCHESTRATOR_API_CONTRACT_VERSION
from llm_orchestrator.exceptions import GuardrailViolation
from llm_orchestrator.service import LLMService
from shared_py.observability import (
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)
from shared_py.observability.request_context import (
    clear_request_context,
    set_request_context,
)


def _ensure_shared_py_path() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    if sp.is_dir():
        s = str(sp)
        if s not in sys.path:
            sys.path.insert(0, s)


_ensure_shared_py_path()


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = LLMOrchestratorSettings()
    bootstrap_from_settings("llm-orchestrator", settings)
    service = LLMService(settings)
    app = FastAPI(
        title="llm-orchestrator",
        version=LLM_ORCHESTRATOR_API_CONTRACT_VERSION,
        description=(
            "Analystenlayer: strukturierte LLM-Ausgaben (JSON-Schema, Validation, Cache, "
            "Circuit-Breaker, Provider-Fallback) mit kuratiertem Retrieval aus docs/llm_knowledge. "
            "Keine Orderhoheit, kein Strategie-Tuning, kein Tool-Calling. "
            "Provider: OpenAI (Prod), Fake nur via LLM_USE_FAKE_PROVIDER (nicht shadow/production)."
        ),
    )
    app.state.service = service
    app.include_router(build_router(service, settings=settings))

    @app.exception_handler(GuardrailViolation)
    async def _guardrail_violation_handler(
        _request: Request, exc: GuardrailViolation
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "GUARDRAIL_VIOLATION",
                    "message": str(exc),
                    "codes": exc.codes,
                }
            },
        )

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        """Gleiche Request-/Correlation-IDs wie Gateway (X-Request-ID) fuer Logs (corr_* im JSON-Format)."""
        incoming_rid = (request.headers.get("x-request-id") or "").strip()
        incoming_cid = (request.headers.get("x-correlation-id") or "").strip()
        rid = incoming_rid or str(uuid.uuid4())
        cid = incoming_cid or rid
        set_request_context(request_id=rid, correlation_id=cid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            clear_request_context()

    @app.get("/ready")
    def ready() -> dict[str, object]:
        parts = {"redis": check_redis_url(settings.redis_url)}
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    instrument_fastapi(app, "llm-orchestrator")
    return app


app = create_app()
