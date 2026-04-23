from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Annotated, Any

import psycopg
import psycopg.errors
import redis
from config.execution_tier import build_execution_tier_payload
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from psycopg.rows import dict_row
from shared_py.health_warnings_display import build_warnings_display

from api_gateway.auth import GatewayAuthContext, require_operator_aggregate_auth
from api_gateway.config import get_gateway_settings
from api_gateway.gateway_readiness_core import gateway_readiness_core_snapshot
from api_gateway.db import DatabaseHealthError, get_database_url, get_db_health
from api_gateway.db_dashboard_queries import fetch_data_freshness
from api_gateway.db_integration_connectivity import (
    fetch_integration_connectivity_map,
    upsert_integration_connectivity_rows,
)
from api_gateway.db_ops_queries import (
    fetch_alert_outbox_recent,
    fetch_monitor_open_alerts,
    fetch_ops_summary,
)
from api_gateway.integrations_matrix import (
    build_integrations_matrix_payload,
    finalize_integrations_matrix_for_health,
)
from api_gateway.operator_health_pdf import build_operator_health_pdf
from api_gateway.provider_ops_summary import build_provider_ops_summary
from api_gateway.routes_live import STREAMS
from api_gateway.system_health_truth_layer import compute_aggregate_status, truth_layer_meta

logger = logging.getLogger("api_gateway.system_health")

router = APIRouter(prefix="/v1/system", tags=["system"])


def _execution_meta(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload
    checks = payload.get("checks")
    if isinstance(checks, dict):
        source = checks
    out: dict[str, Any] = {}
    for key in (
        "execution_mode",
        "strategy_execution_mode",
        "paper_path_active",
        "shadow_trade_enable",
        "shadow_path_active",
        "live_trade_enable",
        "live_order_submission_enabled",
    ):
        if key in source:
            out[key] = source.get(key)
    return out


def _normalize_probe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "ready" in payload:
        ready = bool(payload.get("ready"))
        failed_checks: list[str] = []
        checks = payload.get("checks") or {}
        if isinstance(checks, dict):
            for key, value in checks.items():
                if isinstance(value, dict) and "ok" in value and not bool(value.get("ok")):
                    detail = str(value.get("detail") or "failed")
                    failed_checks.append(f"{key}:{detail}")
                elif isinstance(value, (list, tuple)) and value and not bool(value[0]):
                    detail = value[1] if len(value) > 1 else "failed"
                    failed_checks.append(f"{key}:{detail}")
        result = {
            "status": "ok" if ready else "error",
            "ready": ready,
            "failed_checks": failed_checks,
        }
        result.update(_execution_meta(payload))
        return result

    service_status = str(payload.get("status", "")).strip().lower()
    if service_status in {"ok", "degraded", "error"}:
        result = {"status": service_status, "service_status": service_status}
        result.update(_execution_meta(payload))
        return result

    result = {"status": "ok"}
    result.update(_execution_meta(payload))
    return result


def _probe_http(url: str) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "api-gateway-health/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_body = resp.read(4096)
            ms = int((time.monotonic() - t0) * 1000)
            payload: dict[str, Any] | None = None
            if raw_body:
                try:
                    parsed = json.loads(raw_body.decode("utf-8"))
                    if isinstance(parsed, dict):
                        payload = parsed
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = None

            result: dict[str, Any] = {
                "status": "ok",
                "latency_ms": ms,
                "http_status": resp.status,
            }
            if payload is not None:
                result.update(_normalize_probe_payload(payload))
                for key in ("bitget_ws_stream", "private_ws"):
                    if key in payload:
                        result[key] = payload[key]
            return result
    except urllib.error.HTTPError as e:
        ms = int((time.monotonic() - t0) * 1000)
        return {"status": "degraded", "latency_ms": ms, "http_status": e.code}
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        return {"status": "error", "latency_ms": ms, "detail": str(exc)[:200]}


def _redis_streams_length() -> dict[str, Any]:
    out: dict[str, Any] = {"redis": "skipped", "streams": []}
    rurl = get_gateway_settings().redis_url.strip()
    if not rurl:
        return out
    try:
        from shared_py.redis_client import get_or_create_sync_pooled_client

        r = get_or_create_sync_pooled_client(
            rurl,
            role="gateway_system_health_streams",
            decode_responses=True,
            max_connections=16,
        )
        if not r.ping():
            out["redis"] = "error"
            return out
        out["redis"] = "ok"
        lens: list[dict[str, Any]] = []
        for key in STREAMS:
            try:
                ln = int(r.xlen(key))
                lens.append({"name": key, "length": ln})
            except redis.ResponseError:
                lens.append({"name": key, "length": None, "error": "not_a_stream_or_missing"})
        lens.sort(key=lambda x: -(x.get("length") or 0))
        out["streams"] = lens[:10]
        # optional: discover more events:* streams
        extra = 0
        for _sk in r.scan_iter(match="events:*", count=50):
            extra += 1
            if extra > 40:
                break
        out["events_key_scan_sample"] = extra
    except Exception as exc:
        out["redis"] = "error"
        out["detail"] = str(exc)[:200]
    return out


def _service_definitions() -> list[tuple[str, str | None]]:
    g = get_gateway_settings()
    return [
        ("api-gateway", None),
        ("market-stream", g.health_url_market_stream or None),
        ("feature-engine", g.health_url_feature_engine or None),
        ("structure-engine", g.health_url_structure_engine or None),
        ("signal-engine", g.health_url_signal_engine or None),
        ("drawing-engine", g.health_url_drawing_engine or None),
        ("news-engine", g.health_url_news_engine or None),
        ("llm-orchestrator", g.health_url_llm_orchestrator or None),
        ("paper-broker", g.health_url_paper_broker or None),
        ("learning-engine", g.health_url_learning_engine or None),
        ("alert-engine", g.health_url_alert_engine or None),
        ("monitor-engine", g.health_url_monitor_engine or None),
        ("live-broker", g.health_url_live_broker or None),
    ]


def _integrations_matrix_without_db_persist(
    g: Any,
    services: list[dict[str, Any]],
    *,
    db_status: str,
    redis_st: str,
    ops_summary: dict[str, Any],
    server_now: datetime,
    server_ts_ms: int,
) -> dict[str, Any] | None:
    """API-Zeilen ohne DB-Upsert finalisieren (Fallback bei Persistenz-Fehler)."""
    try:
        api_rows, upsert_b = build_integrations_matrix_payload(
            g,
            services,
            database_status=db_status,
            redis_status=redis_st,
            ops_summary=ops_summary,
        )
        im, _ = finalize_integrations_matrix_for_health(
            api_rows,
            upsert_b,
            {},
            g=g,
            server_now=server_now,
            server_ts_ms=server_ts_ms,
        )
        return im
    except Exception as exc:
        logger.warning("integrations matrix (ohne DB-Persistenz): %s", exc)
        return None


def compute_system_health_payload() -> dict[str, Any]:
    g = get_gateway_settings()
    watchlist = g.dashboard_watchlist_symbols_list()
    symbol = (
        (g.dashboard_default_symbol or g.next_public_default_symbol or (watchlist[0] if watchlist else "")).strip()
        or ""
    )
    server_ts_ms = int(time.time() * 1000)
    db_status = "error"
    freshness: dict[str, Any] = {}
    ops_summary: dict[str, Any] = {
        "monitor": {"open_alert_count": 0},
        "alert_engine": {
            "outbox_pending": 0,
            "outbox_failed": 0,
            "outbox_sending": 0,
        },
        "live_broker": {
            "latest_reconcile_status": None,
            "latest_reconcile_created_ts": None,
            "latest_reconcile_age_ms": None,
            "latest_reconcile_drift_total": 0,
            "active_kill_switch_count": 0,
            "safety_latch_active": False,
            "last_fill_created_ts": None,
            "last_fill_age_ms": None,
            "critical_audit_count_24h": 0,
            "order_status_counts": {},
        },
    }
    dsn = get_database_url()
    database_schema: dict[str, Any] | None = None
    try:
        h = get_db_health()
        database_schema = {
            "status": h.get("status"),
            "missing_tables": h.get("missing_tables", []),
            "pending_migrations": h.get("pending_migrations", []),
            "pending_migrations_preview": h.get("pending_migrations_preview", []),
            "migration_catalog_available": h.get("migration_catalog_available"),
            "expected_migration_files": h.get("expected_migration_files"),
            "applied_migration_files": h.get("applied_migration_files"),
            "schema_core_ok": h.get("schema_core_ok"),
            "migrations_fully_applied": h.get("migrations_fully_applied"),
            "tables": h.get("tables"),
        }
        if h.get("status") == "ok":
            db_status = "ok"
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
                freshness = fetch_data_freshness(conn, symbol=symbol)
                ops_summary = fetch_ops_summary(conn)
        else:
            freshness = {
                "last_candle_ts_ms": None,
                "last_signal_ts_ms": None,
                "last_news_ts_ms": None,
            }
    except DatabaseHealthError as exc:
        logger.warning("system health db: %s", exc)
        database_schema = {
            "status": "error",
            "connect_error": str(exc)[:400],
        }
        freshness = {
            "last_candle_ts_ms": None,
            "last_signal_ts_ms": None,
            "last_news_ts_ms": None,
        }
    except Exception as exc:
        logger.warning("system health db: %s", exc)
        if database_schema is None:
            database_schema = {"status": "error", "connect_error": str(exc)[:400]}
        freshness = {
            "last_candle_ts_ms": None,
            "last_signal_ts_ms": None,
            "last_news_ts_ms": None,
        }

    redis_block = _redis_streams_length()
    redis_st = str(redis_block.get("redis") or "skipped")
    core_snap = gateway_readiness_core_snapshot()
    readiness_core_ok = bool(core_snap.get("core_ok"))
    services: list[dict[str, Any]] = []
    for name, url in _service_definitions():
        if name == "api-gateway":
            services.append(
                {
                    "name": name,
                    "status": "ok" if readiness_core_ok else "error",
                    "configured": True,
                    "note": "self",
                    "core": {"database": db_status, "redis": redis_st},
                }
            )
            continue
        if not url:
            services.append({"name": name, "status": "not_configured", "configured": False})
            continue
        probe = _probe_http(url)
        services.append({"name": name, "url": url, "configured": True, **probe})

    stale_warnings: list[str] = []
    if db_status != "ok":
        spec = False
        if database_schema:
            if database_schema.get("connect_error"):
                stale_warnings.append("schema_connect_failed")
                spec = True
            if database_schema.get("missing_tables"):
                stale_warnings.append("schema_missing_core_tables")
                spec = True
            if database_schema.get("pending_migrations"):
                stale_warnings.append("schema_pending_migrations")
                spec = True
        if not spec:
            stale_warnings.append("schema_database_unhealthy")
    max_age_ms = int(g.data_stale_warn_ms)
    if db_status == "ok":
        for key, label in (
            ("last_candle_ts_ms", "candles"),
            ("last_signal_ts_ms", "signals"),
            ("last_news_ts_ms", "news"),
        ):
            ts = freshness.get(key)
            if ts is None:
                stale_warnings.append(f"no_{label}_timestamp")
                continue
            if server_ts_ms - int(ts) > max_age_ms:
                stale_warnings.append(f"stale_{label}")

    live_ops = ops_summary.get("live_broker") if isinstance(ops_summary, dict) else {}
    if isinstance(live_ops, dict):
        latest_reconcile_status = str(live_ops.get("latest_reconcile_status") or "").strip().lower()
        if latest_reconcile_status and latest_reconcile_status != "ok":
            stale_warnings.append(f"live_broker_reconcile_{latest_reconcile_status}")
        if int(live_ops.get("active_kill_switch_count") or 0) > 0:
            stale_warnings.append("live_broker_kill_switch_active")
        if bool(live_ops.get("safety_latch_active")):
            stale_warnings.append("live_broker_safety_latch_active")
        if int(live_ops.get("critical_audit_count_24h") or 0) > 0:
            stale_warnings.append("live_broker_critical_audits_open")
    monitor_ops = ops_summary.get("monitor") if isinstance(ops_summary, dict) else {}
    if isinstance(monitor_ops, dict) and int(monitor_ops.get("open_alert_count") or 0) > 0:
        stale_warnings.append("monitor_alerts_open")
    alert_ops = ops_summary.get("alert_engine") if isinstance(ops_summary, dict) else {}
    if isinstance(alert_ops, dict) and int(alert_ops.get("outbox_failed") or 0) > 0:
        stale_warnings.append("alert_outbox_failed")

    provider_ops_summary = build_provider_ops_summary(g, services)
    for code in provider_ops_summary.get("hint_codes") or []:
        if isinstance(code, str) and code.strip():
            stale_warnings.append(f"provider:{code.strip()}")

    integrations_matrix: dict[str, Any] | None = None
    server_now = datetime.now(UTC)
    try:
        api_rows, upsert_b = build_integrations_matrix_payload(
            g,
            services,
            database_status=db_status,
            redis_status=redis_st,
            ops_summary=ops_summary,
        )
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            persisted = fetch_integration_connectivity_map(conn)
            integrations_matrix, db_sync = finalize_integrations_matrix_for_health(
                api_rows,
                upsert_b,
                persisted,
                g=g,
                server_now=server_now,
                server_ts_ms=server_ts_ms,
            )
            upsert_integration_connectivity_rows(conn, db_sync)
            conn.commit()
    except psycopg.errors.UndefinedTable:
        integrations_matrix = _integrations_matrix_without_db_persist(
            g,
            services,
            db_status=db_status,
            redis_st=redis_st,
            ops_summary=ops_summary,
            server_now=server_now,
            server_ts_ms=server_ts_ms,
        )
    except Exception as exc:
        logger.warning("integrations matrix: %s", exc)
        integrations_matrix = _integrations_matrix_without_db_persist(
            g,
            services,
            db_status=db_status,
            redis_st=redis_st,
            ops_summary=ops_summary,
            server_now=server_now,
            server_ts_ms=server_ts_ms,
        )

    runtime = g.execution_runtime_snapshot()
    if isinstance(runtime, dict) and not runtime.get("execution_tier"):
        runtime = {**runtime, "execution_tier": build_execution_tier_payload(g)}

    warnings_display = build_warnings_display(stale_warnings, ops_summary=ops_summary)
    aggregate = compute_aggregate_status(
        readiness_core_ok=readiness_core_ok,
        warnings=stale_warnings,
        services=services,
    )
    truth_layer = truth_layer_meta(
        auth_hint_de=(
            "JWT Bearer mit gateway:read oder admin:read; alternativ X-Gateway-Internal-Key mit "
            "entsprechender Rolle (siehe require_operator_aggregate_auth). Ohne erzwungene Auth "
            "(nicht produktiv): anonym moeglich."
        ),
    )
    return {
        "server_ts_ms": server_ts_ms,
        "symbol": symbol.upper(),
        "truth_layer": truth_layer,
        "aggregate": aggregate,
        "readiness_core": {
            "ok": readiness_core_ok,
            "database": db_status,
            "redis": redis_st,
            "checks": core_snap.get("checks"),
            "contract_version": core_snap.get("contract_version"),
            "note": (
                None
                if readiness_core_ok
                else (
                    "Kern-Readiness nicht ok — checks entsprechen GET /ready ohne Peer-URLs; "
                    "Peer-Status nur dort. database/redis: operative Labels aus Schema- bzw. Stream-Sonde."
                )
            ),
        },
        "execution": {
            "execution_mode": g.execution_mode,
            "strategy_execution_mode": g.strategy_execution_mode,
            "paper_path_active": g.paper_path_active,
            "shadow_trade_enable": g.shadow_trade_enable,
            "shadow_path_active": g.shadow_path_active,
            "live_trade_enable": g.live_trade_enable,
            "live_order_submission_enabled": g.live_order_submission_enabled,
            "execution_runtime": runtime,
        },
        "market_universe": g.market_universe_snapshot(),
        "database": db_status,
        "database_schema": database_schema,
        "data_freshness": freshness,
        "redis": redis_block.get("redis"),
        "stream_lengths_top": redis_block.get("streams", []),
        "redis_streams_detail": redis_block,
        "services": services,
        "ops": ops_summary,
        "provider_ops_summary": provider_ops_summary,
        "warnings": stale_warnings,
        "warnings_display": warnings_display,
        "integrations_matrix": integrations_matrix,
    }


@router.get("/health")
def system_health(
    _auth: Annotated[GatewayAuthContext, Depends(require_operator_aggregate_auth)],
) -> dict[str, Any]:
    return compute_system_health_payload()


@router.get("/health/operator-report.pdf")
def system_health_operator_report_pdf(
    _auth: Annotated[GatewayAuthContext, Depends(require_operator_aggregate_auth)],
) -> Response:
    """
    PDF-Export fuer Operator/KI: Warnungen, Massnahmen, machine-JSON, Alerts, Outbox.
    Gleiche Autorisierung wie GET /v1/system/health.
    """
    payload = compute_system_health_payload()
    open_alerts: list[dict[str, Any]] = []
    outbox_rows: list[dict[str, Any]] = []
    if payload.get("database") == "ok":
        try:
            dsn = get_database_url()
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
                open_alerts = fetch_monitor_open_alerts(conn, limit=120)
                outbox_rows = fetch_alert_outbox_recent(conn, limit=60)
        except Exception as exc:
            logger.warning("operator report pdf: extra db reads: %s", exc)
    gen_ts = datetime.now(UTC).replace(microsecond=0).isoformat()
    pdf_bytes = build_operator_health_pdf(
        health=payload,
        open_alerts=open_alerts,
        outbox_rows=outbox_rows,
        generated_at_iso=gen_ts,
    )
    fname = f"operator-health-{gen_ts.replace(':', '-')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Cache-Control": "no-store",
        },
    )
