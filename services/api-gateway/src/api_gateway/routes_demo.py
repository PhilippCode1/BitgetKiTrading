from __future__ import annotations

from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_live_broker_queries import (
    fetch_live_broker_decisions,
    fetch_live_broker_fills,
    fetch_live_broker_orders,
    fetch_live_broker_runtime,
)
from api_gateway.db_market_universe_queries import fetch_market_universe_status
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _is_demo_endpoint(url: str) -> bool:
    lower = (url or "").strip().lower()
    return bool(lower) and ("bitget.com" in lower)


def _settings_snapshot() -> dict[str, Any]:
    s = get_gateway_settings()
    execution_mode = str(s.execution_mode or "").strip().lower()
    demo_enabled = bool(s.bitget_demo_enabled)
    live_trade_enable = bool(s.live_trade_enable)
    demo_rest = str(getattr(s, "bitget_demo_rest_base_url", "") or "")
    live_rest = str(getattr(s, "bitget_api_base_url", "") or "")
    blockers: list[str] = []
    if execution_mode != "bitget_demo":
        blockers.append("EXECUTION_MODE ist nicht bitget_demo.")
    if not demo_enabled:
        blockers.append("BITGET_DEMO_ENABLED ist nicht aktiv.")
    if live_trade_enable:
        blockers.append("LIVE_TRADE_ENABLE muss false sein.")
    if not _is_demo_endpoint(demo_rest):
        blockers.append("BITGET_DEMO_REST_BASE_URL ist unklar oder leer.")
    return {
        "execution_mode": execution_mode,
        "bitget_demo_enabled": demo_enabled,
        "live_trade_enable": live_trade_enable,
        "demo_rest_base_url_hint": ("set" if demo_rest else "missing"),
        "live_rest_base_url_hint": ("set" if live_rest else "missing"),
        "demo_endpoint_clear": _is_demo_endpoint(demo_rest),
        "ready_for_demo_submit": len(blockers) == 0,
        "blockgruende_de": blockers,
    }


def _runtime_bundle() -> dict[str, Any]:
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        runtime = fetch_live_broker_runtime(conn)
        orders = fetch_live_broker_orders(conn, limit=20)
        fills = fetch_live_broker_fills(conn, limit=20)
        decisions = fetch_live_broker_decisions(conn, limit=20)
        universe = fetch_market_universe_status(
            conn, configuration_snapshot=get_gateway_settings().market_universe_snapshot()
        )
    return {
        "runtime": runtime,
        "orders": orders,
        "fills": fills,
        "decisions": decisions,
        "universe": universe,
    }


def _db_error_envelope(message: str, reason: str) -> dict[str, Any]:
    return merge_read_envelope(
        {"demo_mode": _settings_snapshot()},
        status="degraded",
        message=message,
        empty_state=True,
        degradation_reason=reason,
        next_step=NEXT_STEP_DB,
    )


@router.get("/status", response_model=None)
def demo_status(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    mode = _settings_snapshot()
    try:
        data = _runtime_bundle()
    except DatabaseHealthError:
        return _db_error_envelope(
            "Demo-Status ohne Datenbank nicht vollstaendig lesbar.",
            "database_url_missing",
        )
    except Exception:
        return _db_error_envelope(
            "Demo-Status konnte nicht vollstaendig geladen werden.",
            "database_error",
        )
    payload = {
        "demo_mode": mode,
        "demo_connection_status": (
            (data["runtime"] or {}).get("bitget_private_status", {}).get("ui_status") or "unknown"
        ),
        "demo_account": (data["runtime"] or {}).get("bitget_private_status", {}),
        "latest_reconcile": {
            "status": (data["runtime"] or {}).get("status"),
            "snapshot_id": (data["runtime"] or {}).get("reconcile_snapshot_id"),
        },
        "latest_demo_orders": data["orders"],
        "latest_demo_fills": data["fills"],
        "latest_risk_decisions": data["decisions"],
    }
    return merge_read_envelope(payload, status="ok")


@router.get("/readiness", response_model=None)
def demo_readiness(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    mode = _settings_snapshot()
    result = "PASS" if mode["ready_for_demo_submit"] else "FAIL"
    return merge_read_envelope(
        {
            "result": result,
            "demo_mode": mode,
            "hinweis_de": (
                "Demo-Modus ist fuer Read-only verfuegbar."
                if result == "PASS"
                else "Demo-Modus ist nicht submit-bereit; Orders bleiben blockiert."
            ),
        },
        status="ok" if result == "PASS" else "degraded",
        degradation_reason=None if result == "PASS" else "demo_readiness_failed",
        empty_state=False,
    )


@router.get("/assets", response_model=None)
def demo_assets(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    try:
        data = _runtime_bundle()
    except DatabaseHealthError:
        return _db_error_envelope(
            "Demo-Assets ohne Datenbank nicht verfuegbar.",
            "database_url_missing",
        )
    except Exception:
        return _db_error_envelope("Demo-Assets konnten nicht geladen werden.", "database_error")
    instruments = (data["universe"] or {}).get("instruments") or []
    rows = []
    for item in instruments:
        rows.append(
            {
                "symbol": item.get("symbol"),
                "market_family": item.get("market_family"),
                "product_type": item.get("product_type"),
                "status": item.get("trading_status") or "unklar",
                "demo_handelbar": bool(item.get("paper_shadow_eligible")),
                "live_blockiert": not bool(item.get("live_execution_enabled")),
                "risiko_tier": None,
                "datenqualitaet": "unbekannt",
                "block_grund_de": (
                    "Live-Ausfuehrung ist fuer dieses Instrument nicht freigegeben."
                    if not bool(item.get("live_execution_enabled"))
                    else ""
                ),
            }
        )
    return merge_read_envelope({"items": rows, "count": len(rows)}, status="ok")


@router.get("/balance", response_model=None)
def demo_balance(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    try:
        data = _runtime_bundle()
    except DatabaseHealthError:
        return _db_error_envelope("Demo-Balance ist ohne Datenbank nicht abrufbar.", "database_url_missing")
    except Exception:
        return _db_error_envelope("Demo-Balance konnte nicht geladen werden.", "database_error")
    runtime = data["runtime"] or {}
    account = runtime.get("bitget_private_status") or {}
    return merge_read_envelope(
        {
            "balance_hint": account.get("private_auth_detail_de") or "Keine Balance-Daten im Runtime-Snapshot.",
            "demo_account_status": account.get("ui_status") or "unknown",
        },
        status="ok",
    )


@router.get("/positions", response_model=None)
def demo_positions(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    # Positionen werden in diesem Repo derzeit primär über Reconcile/Orders/Fills geführt.
    return merge_read_envelope(
        {
            "items": [],
            "hinweis_de": "Direkte Demo-Positionsliste ist noch nicht separat verdrahtet; bitte Reconcile/Fills nutzen.",
        },
        status="empty",
        empty_state=True,
        degradation_reason="demo_positions_not_wired",
    )


@router.get("/open-orders", response_model=None)
def demo_open_orders(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    try:
        data = _runtime_bundle()
    except DatabaseHealthError:
        return _db_error_envelope(
            "Demo-Open-Orders sind ohne Datenbank nicht abrufbar.",
            "database_url_missing",
        )
    except Exception:
        return _db_error_envelope("Demo-Open-Orders konnten nicht geladen werden.", "database_error")
    items = [o for o in (data["orders"] or []) if str(o.get("status") or "").lower() not in ("filled", "canceled")]
    return merge_read_envelope({"items": items, "count": len(items)}, status="ok")


@router.get("/order-history", response_model=None)
def demo_order_history(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    try:
        data = _runtime_bundle()
    except DatabaseHealthError:
        return _db_error_envelope(
            "Demo-Order-Historie ist ohne Datenbank nicht abrufbar.",
            "database_url_missing",
        )
    except Exception:
        return _db_error_envelope("Demo-Order-Historie konnte nicht geladen werden.", "database_error")
    return merge_read_envelope({"items": data["orders"] or [], "count": len(data["orders"] or [])}, status="ok")


@router.post("/order/preview", response_model=None)
def demo_order_preview(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    mode = _settings_snapshot()
    return merge_read_envelope(
        {
            "allowed": mode["ready_for_demo_submit"],
            "demo_mode": mode,
            "hinweis_de": (
                "Preview ist verfuegbar; Submit bleibt separat abgesichert."
                if mode["ready_for_demo_submit"]
                else "Preview nur eingeschraenkt, weil Demo-Grundlagen fehlen."
            ),
        },
        status="ok" if mode["ready_for_demo_submit"] else "degraded",
        degradation_reason=None if mode["ready_for_demo_submit"] else "demo_preview_blocked",
    )


@router.post("/order/submit", response_model=None)
def demo_order_submit_blocked(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    mode = _settings_snapshot()
    reasons = list(mode.get("blockgruende_de") or [])
    reasons.append("Demo-Order-Submit ist serverseitig noch nicht freigegeben (Safety-First).")
    return merge_read_envelope(
        {
            "allowed": False,
            "blockgruende_de": reasons,
            "live_trading_status_de": "Echtes Live-Trading bleibt AUS.",
        },
        status="degraded",
        empty_state=False,
        degradation_reason="demo_submit_not_released",
    )


@router.post("/order/cancel", response_model=None)
def demo_order_cancel_blocked(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    return merge_read_envelope(
        {
            "allowed": False,
            "blockgruende_de": [
                "Demo-Cancel ist noch nicht freigegeben, bis Demo-Submit-Ende-zu-Ende auditiert ist."
            ],
        },
        status="degraded",
        degradation_reason="demo_cancel_not_released",
    )
