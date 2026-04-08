from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import APIRouter
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_live_queries import fetch_online_drift_state_row
from api_gateway.db_dashboard_queries import (
    fetch_backtest_runs,
    fetch_drift_recent,
    fetch_error_patterns_top,
    fetch_learning_strategy_metrics,
    fetch_model_ops_report,
    fetch_model_registry_v2_slots,
    fetch_recommendations_recent,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from shared_py.learning_drift_api import (
    drift_recent_response,
    gateway_online_drift_state_response,
)

logger = logging.getLogger("api_gateway.learning_proxy")

learning_router = APIRouter(prefix="/v1/learning", tags=["learning"])
backtest_router = APIRouter(prefix="/v1/backtests", tags=["backtests"])


def _lim(default: int, cap: int) -> int:
    try:
        return max(1, min(cap, int(get_gateway_settings().dashboard_page_size or default)))
    except ValueError:
        return default


def _degraded_learning(
    *,
    fallback: dict[str, Any],
    reason: str,
    msg: str,
) -> dict[str, Any]:
    return merge_read_envelope(
        fallback,
        status="degraded",
        message=msg,
        empty_state=True,
        degradation_reason=reason,
        next_step=NEXT_STEP_DB,
    )


@learning_router.get("/models/registry-v2", response_model=None)
def learning_model_registry_v2() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        cap = _lim(20, 100)
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_model_registry_v2_slots(conn, limit=cap)
        payload = {"items": items, "limit": cap}
        es = len(items) == 0
        return merge_read_envelope(
            payload,
            status="ok",
            message="Keine Registry-Slots geladen." if es else None,
            empty_state=es,
            degradation_reason="no_registry_slots" if es else None,
            next_step="Model-Registry befuellen oder anderen Scope pruefen." if es else None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning registry-v2: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(20, 100)},
            reason="database_url_missing",
            msg="Datenbank ist nicht konfiguriert.",
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("learning registry-v2: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(20, 100)},
            reason="database_error",
            msg="Registry konnte nicht geladen werden.",
        )


@learning_router.get("/metrics/strategies", response_model=None)
def learning_metrics_strategies() -> dict[str, Any]:
    try:
        lim = _lim(50, 200)
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_learning_strategy_metrics(conn, limit=lim)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": lim},
            status="ok",
            message="Keine Strategie-Metriken vorhanden." if es else None,
            empty_state=es,
            degradation_reason="no_strategy_metrics" if es else None,
            next_step="Learning-Pipeline und Strategien pruefen." if es else None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning metrics/strategies: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(50, 200)},
            reason="database_url_missing",
            msg="Datenbank ist nicht konfiguriert.",
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("learning metrics/strategies: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(50, 200)},
            reason="database_error",
            msg="Metriken konnten nicht geladen werden.",
        )


@learning_router.get("/patterns/top", response_model=None)
def learning_patterns_top() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_error_patterns_top(conn, limit=10)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": 10},
            status="ok",
            message="Keine Fehlermuster im Fenster." if es else None,
            empty_state=es,
            degradation_reason="no_error_patterns" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning patterns: %s", exc)
        return _degraded_learning(fallback={"items": [], "limit": 10}, reason="database_url_missing", msg="Datenbank ist nicht konfiguriert.")
    except (pg_errors.Error, OSError) as exc:
        logger.warning("learning patterns: %s", exc)
        return _degraded_learning(fallback={"items": [], "limit": 10}, reason="database_error", msg="Muster konnten nicht geladen werden.")


@learning_router.get("/recommendations/recent", response_model=None)
def learning_recommendations_recent() -> dict[str, Any]:
    try:
        lim = _lim(50, 200)
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_recommendations_recent(conn, limit=lim)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": lim},
            status="ok",
            message="Keine Empfehlungen vorhanden." if es else None,
            empty_state=es,
            degradation_reason="no_recommendations" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning recommendations: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(50, 200)},
            reason="database_url_missing",
            msg="Datenbank ist nicht konfiguriert.",
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("learning recommendations: %s", exc)
        return _degraded_learning(
            fallback={"items": [], "limit": _lim(50, 200)},
            reason="database_error",
            msg="Empfehlungen konnten nicht geladen werden.",
        )


@learning_router.get(
    "/drift/recent",
    response_model=None,
    summary="Drift-Events (recent)",
    description="Letzte Eintraege aus learn.drift_events. Payload siehe docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md.",
)
def learning_drift_recent() -> dict[str, Any]:
    limit = 50
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_drift_recent(conn, limit=limit)
        raw = drift_recent_response(items=items, limit=limit)
        es = len(items) == 0
        return merge_read_envelope(
            raw,
            status="ok",
            message="Keine Drift-Events in der Datenbank." if es else None,
            empty_state=es,
            degradation_reason="no_drift_events" if es else None,
            next_step="Monitor und Online-Drift-Evaluator laufen lassen." if es else None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning drift/recent: %s", exc)
        raw = drift_recent_response(items=[], limit=limit)
        return merge_read_envelope(
            raw,
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.UndefinedTable, psycopg.OperationalError, OSError) as exc:
        logger.warning("learning drift/recent degraded: %s", exc)
        raw = drift_recent_response(items=[], limit=limit)
        return merge_read_envelope(
            raw,
            status="degraded",
            message="Drift-Events konnten nicht gelesen werden (Tabelle fehlt oder DB nicht erreichbar).",
            empty_state=True,
            degradation_reason="drift_query_failed",
            next_step=NEXT_STEP_DB,
        )


@learning_router.get("/model-ops/report", response_model=None)
def learning_model_ops_report(slice_hours: int = 168) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            report = fetch_model_ops_report(conn, slice_hours=slice_hours)
        return merge_read_envelope(
            report if isinstance(report, dict) else {"report": report},
            status="ok",
            message=None,
            empty_state=False,
            degradation_reason=None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning model-ops: %s", exc)
        return merge_read_envelope(
            {},
            status="degraded",
            message="Model-Ops-Report nicht ladbar: Datenbank fehlt.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("learning model-ops: %s", exc)
        return merge_read_envelope(
            {},
            status="degraded",
            message="Model-Ops-Report voruebergehend nicht verfuegbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@learning_router.get(
    "/drift/online-state",
    response_model=None,
    summary="Online-Drift-Zustand",
    description="Zeile aus learn.online_drift_state oder item=null. HTTP 200; leerer State ist erwartbar vor Evaluator-Lauf.",
)
def learning_drift_online_state() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_online_drift_state_row(conn)
        raw = gateway_online_drift_state_response(row)
        empty = raw.get("item") is None
        return merge_read_envelope(
            raw,
            status="ok",
            message="Kein materialisierter Online-Drift-State (Zeile fehlt)." if empty else None,
            empty_state=empty,
            degradation_reason="no_online_drift_row" if empty else None,
            next_step="Migration 400 und POST /learning/drift/evaluate-now auf der Learning-Engine ausfuehren." if empty else None,
        )
    except DatabaseHealthError as exc:
        logger.warning("learning drift/online-state: %s", exc)
        raw = gateway_online_drift_state_response(None)
        return merge_read_envelope(
            raw,
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.UndefinedTable, psycopg.OperationalError, OSError) as exc:
        logger.warning("learning drift/online-state degraded: %s", exc)
        raw = gateway_online_drift_state_response(None)
        return merge_read_envelope(
            raw,
            status="degraded",
            message="Online-Drift-State nicht lesbar.",
            empty_state=True,
            degradation_reason="online_drift_query_failed",
            next_step=NEXT_STEP_DB,
        )


@backtest_router.get("/runs", response_model=None)
def backtest_runs() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_backtest_runs(conn, limit=10)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": 10},
            status="ok",
            message="Keine Backtest-Laeufe gefunden." if es else None,
            empty_state=es,
            degradation_reason="no_backtest_runs" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("backtests runs: %s", exc)
        return _degraded_learning(fallback={"items": [], "limit": 10}, reason="database_url_missing", msg="Datenbank ist nicht konfiguriert.")
    except (pg_errors.Error, OSError) as exc:
        logger.warning("backtests runs: %s", exc)
        return _degraded_learning(fallback={"items": [], "limit": 10}, reason="database_error", msg="Backtests konnten nicht geladen werden.")
