from __future__ import annotations

# ruff: noqa: E402, I001 — Bootstrap-Reihenfolge / Import-Blocks
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _ensure_monorepo_root() -> None:
    root = Path(__file__).resolve().parents[4]
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)


_ensure_monorepo_root()
from config.bootstrap import bootstrap_from_settings
from fastapi.middleware.cors import CORSMiddleware
from shared_py.observability import (
    append_peer_readiness_checks,
    clear_request_context,
    instrument_fastapi,
    log_correlation_fields,
    merge_ready_details,
    set_request_context,
)

from api_gateway.auth import require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.gateway_readiness_core import (
    READINESS_CONTRACT_VERSION,
    gateway_readiness_core_parts_resilient,
)
from api_gateway.errors import http_error_envelope, shape_http_exception
from api_gateway.gateway_read_envelope import merge_read_envelope
from api_gateway.rate_limit import GatewayRateLimitMiddleware
from api_gateway.security_headers import SecurityHeadersMiddleware
from api_gateway.routes_admin import router as admin_router
from api_gateway.routes_admin_paper import router as admin_paper_router
from api_gateway.routes_auth import router as auth_router
from api_gateway.routes_commerce import router as commerce_router
from api_gateway.routes_commerce_customer import (
    admin_customer_router,
    customer_router,
)
from api_gateway.routes_commercial_contracts import (
    contract_admin_router,
    contract_customer_router,
    contract_webhook_router,
)
from api_gateway.routes_commerce_subscription_billing import (
    billing_admin_router,
    billing_customer_router,
)
from api_gateway.routes_commerce_payments import payments_admin_router, payments_router
from api_gateway.routes_commerce_profit_fee import (
    profit_fee_admin_router,
    profit_fee_customer_router,
)
from api_gateway.routes_commerce_settlement import (
    settlement_admin_router,
    treasury_admin_router,
)
from api_gateway.routes_correlation_proxy import router as correlation_proxy_router
from api_gateway.routes_alerts_proxy import router as alerts_proxy_router
from api_gateway.routes_apex_trace import router as apex_trace_router
from api_gateway.routes_db import router as db_router
from api_gateway.routes_events import router as events_router
from api_gateway.routes_learning_proxy import backtest_router, learning_router
from api_gateway.routes_live import router as live_router
from api_gateway.routes_live_broker_operator import router as live_broker_operator_router
from api_gateway.routes_live_broker_proxy import router as live_broker_proxy_router
from api_gateway.routes_live_broker_safety import router as live_broker_safety_router
from api_gateway.routes_demo import router as demo_router
from api_gateway.routes_market_universe import router as market_universe_router
from api_gateway.routes_monitor_proxy import router as monitor_proxy_router
from api_gateway.routes_news_proxy import router as news_proxy_router
from api_gateway.routes_paper_proxy import router as paper_proxy_router
from api_gateway.routes_registry_proxy import router as registry_proxy_router
from api_gateway.routes_signals_proxy import router as signals_proxy_router
from api_gateway.routes_deploy_readiness import router as deploy_readiness_router
from api_gateway.routes_llm_assist import router as llm_assist_router
from api_gateway.routes_ai_strategy_proposal_drafts import (
    router as ai_strategy_proposal_drafts_router,
)
from api_gateway.routes_llm_operator import router as llm_operator_router
from api_gateway.routes_public_meta import router as public_meta_router
from api_gateway.routes_ops_self_healing import router as ops_self_healing_router
from api_gateway.routes_system_health import router as system_health_router

bootstrap_from_settings("api-gateway", get_gateway_settings())
logger = logging.getLogger("api_gateway")


def create_app() -> FastAPI:
    settings = get_gateway_settings()

    @asynccontextmanager
    async def _gateway_lifespan(app: FastAPI):
        dsn = (settings.database_url or "").strip() or (
            str(getattr(settings, "database_url_docker", "") or "").strip()
        )
        _s = (os.environ.get("BITGET_SKIP_MIGRATION_LATCH") or "").strip().lower()
        skip = _s in ("1", "true", "yes", "on")
        if dsn and not skip:
            from shared_py.datastore.sqlalchemy_async import create_pooled_async_engine
            from shared_py.migration_latch import assert_repo_migrations_applied_async

            eng = create_pooled_async_engine(dsn)
            app.state.db_async_engine = eng
            try:
                await assert_repo_migrations_applied_async(eng)
            except Exception:
                await eng.dispose()
                app.state.db_async_engine = None
                raise
        else:
            app.state.db_async_engine = None
        try:
            yield
        finally:
            eng = getattr(app.state, "db_async_engine", None)
            if eng is not None:
                await eng.dispose()
                app.state.db_async_engine = None

    app = FastAPI(
        title="bitget-btc-ai API Gateway",
        version="0.2.0",
        lifespan=_gateway_lifespan,
        description=(
            "Zentrale HTTP-Schicht fuer Dashboard und Operator. "
            "Leser-Envelope und Beispiel-Payloads: docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md — "
            "Sicherheit: docs/api_gateway_security.md — Zahlungen: docs/payment_architecture.md."
        ),
        openapi_tags=[
            {"name": "system", "description": "Aggregierte Gesundheit und Ops-Sicht."},
            {"name": "learning", "description": "Learning-Metriken, Drift, Registry, Backtests."},
            {"name": "monitor", "description": "Monitor-Alerts und Ops-Lesepfade."},
            {"name": "paper", "description": "Paper-Broker-Lesepfade."},
            {"name": "live", "description": "Live-Zustand und SSE (Auth beachten)."},
            {"name": "commerce-customer", "description": "Kundenportal, Guthaben, Einzahlungen (BFF/JWT)."},
            {"name": "commerce-admin-customer", "description": "Admin-Kundenpflege (billing:admin / admin:write)."},
            {
                "name": "commerce-payments",
                "description": (
                    "Zahlungs-Webhooks (Stripe, Mock, Wise, PayPal-Stub) und Admin-Diagnose."
                ),
            },
            {
                "name": "commerce-contracts",
                "description": "Vertrags-PDF, Mock-E-Sign, Webhook (Prompt 12).",
            },
            {
                "name": "commerce-billing",
                "description": "Abo-Preise, 19 % USt, Rechnungen, Finanz-Ledger (Prompt 13).",
            },
            {
                "name": "commerce-profit-fee",
                "description": "Gewinnbeteiligung, High-Water-Mark, Statements (Prompt 15).",
            },
            {
                "name": "commerce-settlement",
                "description": "Treasury-Konfiguration, manuelles Settlement (Prompt 16).",
            },
            {"name": "commerce", "description": "Interne Commerce-/Metering-Endpunkte."},
            {"name": "deploy", "description": "Edge-/Reverse-Proxy-Readiness ohne Secrets."},
            {"name": "meta", "description": "Oeffentliche Laufzeit-Kontur (keine Secrets)."},
            {
                "name": "llm-operator",
                "description": "Operator-KI (Erklaerungen) — JWT gateway:read, Forward zum LLM-Orchestrator.",
            },
        ],
    )

    _cors = settings.cors_allow_origins.strip()
    origins = [o.strip() for o in _cors.split(",") if o.strip()]
    _allow_headers = [
        "authorization",
        "content-type",
        "x-gateway-internal-key",
        "x-admin-token",
        "x-manual-action-token",
        "x-commercial-meter-secret",
        "x-commercial-contract-signature",
        "x-request-id",
        "x-correlation-id",
        "accept",
        "origin",
        "cache-control",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=_allow_headers,
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Gateway-Read-Status",
            "X-Gateway-Degradation-Reason",
        ],
    )
    app.add_middleware(GatewayRateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming_rid = (request.headers.get("x-request-id") or "").strip()
        incoming_cid = (request.headers.get("x-correlation-id") or "").strip()
        rid = incoming_rid or str(uuid.uuid4())
        cid = incoming_cid or rid
        request.state.request_id = rid
        request.state.correlation_id = cid
        set_request_context(request_id=rid, correlation_id=cid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            clear_request_context()

    app.include_router(deploy_readiness_router)
    app.include_router(public_meta_router)

    @app.exception_handler(HTTPException)
    async def _gateway_http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        s = get_gateway_settings()
        return JSONResponse(
            status_code=exc.status_code,
            content=shape_http_exception(production=s.production, exc=exc),
        )

    @app.exception_handler(RequestValidationError)
    async def _gateway_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        s = get_gateway_settings()
        if s.production:
            return JSONResponse(
                status_code=422,
                content=http_error_envelope(
                    status_code=422,
                    code="VALIDATION_ERROR",
                    message="Invalid request body.",
                ),
            )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(Exception)
    async def _gateway_unhandled_read_degrade(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """GET /v1/*: keine rohen 500er mit Stacktrace ans Dashboard — strukturiertes Degrade-Envelope."""
        path = str(request.url.path)
        if request.method == "GET" and path.startswith("/v1/"):
            s = get_gateway_settings()
            rid = getattr(request.state, "request_id", None)
            cid = getattr(request.state, "correlation_id", None)
            logger.exception(
                "unhandled GET %s",
                path,
                extra=log_correlation_fields(
                    request_id=str(rid) if rid else None,
                    correlation_id=str(cid) if cid else None,
                ),
            )
            extra: dict[str, object] = {}
            if not s.production:
                extra["internal_hint"] = f"{type(exc).__name__}: {str(exc)[:400]}"
            body = merge_read_envelope(
                extra,
                status="degraded",
                message="Unerwarteter Fehler beim Lesen dieser Ressource.",
                empty_state=True,
                degradation_reason="unhandled_exception",
                next_step="API-Gateway-Logs und Datenbank/Upstream pruefen.",
            )
            return JSONResponse(status_code=200, content=body)
        rid = getattr(request.state, "request_id", None)
        cid = getattr(request.state, "correlation_id", None)
        logger.exception(
            "unhandled %s %s",
            request.method,
            path,
            extra=log_correlation_fields(
                request_id=str(rid) if rid else None,
                correlation_id=str(cid) if cid else None,
            ),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "code": "INTERNAL_SERVER_ERROR",
                "layer": "api-gateway",
            },
        )

    app.include_router(auth_router)
    app.include_router(commerce_router)
    app.include_router(customer_router)
    app.include_router(admin_customer_router)
    app.include_router(payments_router)
    app.include_router(payments_admin_router)
    app.include_router(contract_customer_router)
    app.include_router(contract_admin_router)
    app.include_router(contract_webhook_router)
    app.include_router(billing_customer_router)
    app.include_router(billing_admin_router)
    app.include_router(profit_fee_customer_router)
    app.include_router(profit_fee_admin_router)
    app.include_router(treasury_admin_router)
    app.include_router(settlement_admin_router)
    app.include_router(db_router)
    app.include_router(events_router)
    app.include_router(apex_trace_router)
    app.include_router(correlation_proxy_router)
    # Live-SSE: bei erzwungenem Auth JWT/Internal-Key oder SSE-Cookie; Dashboard-BFF empfohlen.
    app.include_router(live_router)
    app.include_router(live_broker_proxy_router)
    app.include_router(demo_router)
    app.include_router(live_broker_operator_router)
    app.include_router(live_broker_safety_router)
    app.include_router(
        monitor_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        alerts_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        signals_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        paper_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        news_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        registry_proxy_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        market_universe_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        learning_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        backtest_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(
        ai_strategy_proposal_drafts_router,
        dependencies=[Depends(require_sensitive_auth)],
    )
    app.include_router(llm_operator_router)
    app.include_router(llm_assist_router)
    app.include_router(ops_self_healing_router)
    app.include_router(system_health_router)
    app.include_router(admin_router)
    app.include_router(admin_paper_router)

    instrument_fastapi(app, "api-gateway")

    @app.get("/health")
    def health() -> dict[str, str]:
        """
        Liveness: Prozess laeuft, ASGI antwortet. Keine Postgres/Redis-Pruefung —
        dafuer GET /ready.
        """
        return {
            "status": "ok",
            "service": "api-gateway",
            "role": "liveness",
        }

    @app.get("/ready")
    def ready() -> dict[str, object]:
        s = get_gateway_settings()
        try:
            parts = dict(gateway_readiness_core_parts_resilient())
            parts = append_peer_readiness_checks(
                parts,
                s.readiness_require_urls_raw,
                timeout_sec=float(s.readiness_peer_timeout_sec),
            )
            ok, details = merge_ready_details(parts)
            peer_n = sum(1 for k in parts if k.startswith("upstream_"))
            out: dict[str, object] = {
                "ready": ok,
                "role": "readiness",
                "service": "api-gateway",
                "readiness_contract_version": READINESS_CONTRACT_VERSION,
                "checks": details,
                "summary": {
                    "core_postgres_connect": parts.get("postgres", (False, ""))[0],
                    "core_postgres_schema": parts.get("postgres_schema", (False, ""))[0],
                    "core_redis": parts.get("redis", (False, ""))[0],
                    "peer_checks_configured": peer_n,
                },
            }
            if not s.production:
                out["app_env"] = s.app_env
            return out
        except Exception as exc:  # pragma: no cover - harte Entkopplung: kein 500er bei Hiccup
            logger.exception("readiness probe failed: %s", exc)
            return {
                "ready": False,
                "role": "readiness",
                "service": "api-gateway",
                "readiness_contract_version": READINESS_CONTRACT_VERSION,
                "checks": {
                    "readiness_unhandled": {
                        "ok": False,
                        "detail": str(exc)[:400],
                    }
                },
                "summary": {
                    "core_postgres_connect": False,
                    "core_postgres_schema": False,
                    "core_redis": False,
                    "peer_checks_configured": 0,
                },
            }

    @app.get("/")
    def root() -> dict[str, str]:
        if settings.production:
            return {"service": "api-gateway"}
        return {"service": "api-gateway", "env": settings.app_env}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    s = get_gateway_settings()
    logger.info("uvicorn bind port=%s", s.app_port)
    uvicorn.run(
        "api_gateway.app:app",
        host="0.0.0.0",
        port=s.app_port,
        log_level=s.log_level.lower(),
    )


if __name__ == "__main__":
    main()
