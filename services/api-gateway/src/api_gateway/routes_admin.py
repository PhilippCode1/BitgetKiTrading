from __future__ import annotations

import time
from typing import Annotated, Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_admin_read, require_admin_write
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_customer_performance import fetch_admin_performance_aggregates
from api_gateway.db_admin_console import (
    fetch_contract_review_open_count,
    fetch_customer_notify_outbox_failed_recent,
    fetch_customer_notify_outbox_recent,
    fetch_customer_telegram_binding_count,
    fetch_integration_broker_buckets,
    fetch_integration_telegram_buckets,
    fetch_lifecycle_recent,
    fetch_lifecycle_status_counts,
    fetch_profit_fee_status_counts,
    fetch_subscription_summary,
    fetch_telegram_command_audit_recent,
)
from api_gateway.db_dashboard_queries import (
    fetch_admin_rules,
    update_strategy_status,
    upsert_admin_rules,
)
from api_gateway.llm_orchestrator_forward import (
    LLMOrchestratorForwardHttpError,
    get_llm_orchestrator_json,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_ALLOWED_STATUS = frozenset({"promoted", "candidate", "shadow", "retired"})


class AdminRulesUpsert(BaseModel):
    rule_set_id: str = "default"
    rules_json: dict[str, Any] = Field(default_factory=dict)


class StrategyStatusBody(BaseModel):
    strategy_id: UUID
    new_status: str
    reason: str | None = None
    changed_by: str = "admin-ui"


@router.get("/llm-governance")
def admin_llm_governance_get(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    """
    KI-Governance: Prompt-Versionen, Modellzuordnung, Eval-Hinweis (Orchestrator).
    """
    record_gateway_audit_line(request, auth, "admin_llm_governance_read")
    g = get_gateway_settings()
    try:
        raw = get_llm_orchestrator_json(
            g,
            "/llm/governance/summary",
            timeout_sec=25.0,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_ORCH_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except LLMOrchestratorForwardHttpError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "LLM_ORCH_ERROR",
                "upstream_status": exc.status_code,
                "message": exc.payload,
            },
        ) from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="unexpected orchestrator response")
    return {
        "source": "llm-orchestrator",
        "summary": raw,
        "eval_scores_placeholder": {
            "status": "ci_regression_enforced",
            "hint_de": (
                "Automatische Eval-Scores: pytest tests/llm_eval + tools/validate_eval_baseline.py "
                "im CI; Detailfaelle unter summary.eval_regression.cases. "
                "Persistenter numerischer Score-Store (Zeitreihe) optional."
            ),
        },
    }


@router.get(
    "/performance-overview",
    summary="Aggregierte Paper-/Live-Kennzahlen (Prompt 20, ohne Mandanten-PII)",
)
def admin_performance_overview(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    record_gateway_audit_line(request, auth, "admin_performance_overview_read")
    now_ms = int(time.time() * 1000)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
        return fetch_admin_performance_aggregates(conn, now_ms=now_ms)


@router.get(
    "/telegram-customer-delivery",
    summary="Kunden-Telegram: Outbox, Fehler, letzte Bot-Befehle (Prompt 19)",
)
def admin_telegram_customer_delivery(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    record_gateway_audit_line(request, auth, "admin_telegram_customer_delivery_read")
    dsn = get_database_url()
    payload: dict[str, Any] = {
        "schema_version": "admin-telegram-customer-delivery-v1",
        "bindings_count": None,
        "customer_notify_recent": None,
        "customer_notify_failed_recent": None,
        "command_audit_recent": None,
    }
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
        try:
            payload["bindings_count"] = fetch_customer_telegram_binding_count(conn)
        except psycopg.errors.UndefinedTable:
            payload["bindings_count"] = None
        try:
            payload["customer_notify_recent"] = fetch_customer_notify_outbox_recent(
                conn, limit=40
            )
        except psycopg.errors.UndefinedTable:
            payload["customer_notify_recent"] = None
        try:
            payload["customer_notify_failed_recent"] = fetch_customer_notify_outbox_failed_recent(
                conn, limit=20
            )
        except psycopg.errors.UndefinedTable:
            payload["customer_notify_failed_recent"] = None
        try:
            payload["command_audit_recent"] = fetch_telegram_command_audit_recent(
                conn, limit=35
            )
        except psycopg.errors.UndefinedTable:
            payload["command_audit_recent"] = None
    return payload


@router.get("/console-overview", summary="Admin-Cockpit: Lebenszyklus, Abo, Vertraege, Integrationen")
def admin_console_overview(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    """Aggregierte Kennzahlen fuer das zentrale Admin-Dashboard (ohne Schreibpfade)."""
    record_gateway_audit_line(request, auth, "admin_console_overview_read")
    g = get_gateway_settings()
    dsn = get_database_url()
    payload: dict[str, Any] = {
        "schema_version": "admin-console-overview-v1",
        "commercial_enabled": bool(g.commercial_enabled),
        "profit_fee_module_enabled": bool(getattr(g, "profit_fee_module_enabled", False)),
        "lifecycle": None,
        "subscriptions": None,
        "contracts_review_open": None,
        "profit_fee_by_status": None,
        "integrations_telegram": None,
        "integrations_broker": None,
    }
    if not g.commercial_enabled:
        return payload
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
        try:
            payload["lifecycle"] = {
                "status_counts": fetch_lifecycle_status_counts(conn),
                "recent": fetch_lifecycle_recent(conn, limit=18),
            }
        except psycopg.errors.UndefinedTable:
            payload["lifecycle"] = None
        try:
            payload["subscriptions"] = fetch_subscription_summary(conn)
        except psycopg.errors.UndefinedTable:
            payload["subscriptions"] = None
        try:
            payload["contracts_review_open"] = fetch_contract_review_open_count(conn)
        except psycopg.errors.UndefinedTable:
            payload["contracts_review_open"] = None
        if getattr(g, "profit_fee_module_enabled", False):
            try:
                payload["profit_fee_by_status"] = fetch_profit_fee_status_counts(conn)
            except psycopg.errors.UndefinedTable:
                payload["profit_fee_by_status"] = None
        try:
            payload["integrations_telegram"] = fetch_integration_telegram_buckets(conn)
        except psycopg.errors.UndefinedTable:
            payload["integrations_telegram"] = None
        try:
            payload["integrations_broker"] = fetch_integration_broker_buckets(conn)
        except psycopg.errors.UndefinedTable:
            payload["integrations_broker"] = None
    return payload


@router.get("/rules")
def admin_rules_get(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_read)],
) -> dict[str, Any]:
    record_gateway_audit_line(request, auth, "admin_rules_read")
    g = get_gateway_settings()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        rule_sets = fetch_admin_rules(conn)
    return {
        "rule_sets": rule_sets,
        "env": {
            "DASHBOARD_DEFAULT_TF": g.dashboard_default_tf,
            "DASHBOARD_PAGE_SIZE": str(g.dashboard_page_size),
            "LOG_LEVEL": g.log_level,
            "LIVE_STATE_DEFAULT_CANDLES": str(g.live_state_default_candles),
        },
    }


@router.post("/rules")
def admin_rules_post(
    request: Request,
    body: AdminRulesUpsert,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_write)],
) -> dict[str, Any]:
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        upsert_admin_rules(
            conn, rule_set_id=body.rule_set_id, rules_json=body.rules_json
        )
        conn.commit()
    record_gateway_audit_line(
        request,
        auth,
        "admin_rules_upsert",
        extra={"rule_set_id": body.rule_set_id},
    )
    return {"ok": True, "rule_set_id": body.rule_set_id}


@router.post("/strategy-status")
def admin_strategy_status(
    request: Request,
    body: StrategyStatusBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_write)],
) -> dict[str, Any]:
    if body.new_status not in _ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="invalid new_status")
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        ok = update_strategy_status(
            conn,
            strategy_id=body.strategy_id,
            new_status=body.new_status,
            reason=body.reason,
            changed_by=body.changed_by,
        )
        conn.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="strategy not found")
    record_gateway_audit_line(
        request,
        auth,
        "admin_strategy_status_change",
        extra={
            "strategy_id": str(body.strategy_id),
            "new_status": body.new_status,
            "changed_by": body.changed_by,
        },
    )
    return {
        "ok": True,
        "strategy_id": str(body.strategy_id),
        "new_status": body.new_status,
    }
