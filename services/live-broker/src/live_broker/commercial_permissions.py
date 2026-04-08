"""Laufzeit-Sicht auf kommerzielle Gates (Modul Mate) fuer Health/Ops — ohne Secrets."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from shared_py.modul_mate_db_gates import fetch_tenant_modul_mate_gates
from shared_py.product_policy import (
    order_placement_permissions,
    product_policy_descriptor,
)

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings

logger = logging.getLogger("live_broker.commercial_permissions")


def commercial_runtime_payload(
    settings: LiveBrokerSettings,
    *,
    schema_ready: bool,
) -> dict[str, Any]:
    """
    JSON-freundliche Zusammenfassung: Enforcement-Flags, Policy-Metadaten,
    optional DB-gelesene Tenant-Gates (nur wenn Schema bereit und DSN gesetzt).
    """
    dsn = (settings.database_url or "").strip()
    tid = (settings.modul_mate_gate_tenant_id or "default").strip()
    base: dict[str, Any] = {
        "enforcement": {
            "commercial_gates_enforced_for_exchange_submit": (
                settings.commercial_gates_enforced_for_exchange_submit
            ),
            "modul_mate_gate_enforcement": settings.modul_mate_gate_enforcement,
            "live_broker_require_commercial_gates": (
                settings.live_broker_require_commercial_gates
            ),
        },
        "modul_mate_gate_tenant_id": tid,
        "database_url_configured": bool(dsn),
        "bitget_demo_enabled": settings.bitget_demo_enabled,
        "product_policy": product_policy_descriptor(),
        "tenant_commercial": {
            "status": "skipped",
            "reason": "schema_not_ready_or_no_dsn",
            "tenant_id": tid,
        },
    }

    if not schema_ready or not dsn:
        if not dsn:
            base["tenant_commercial"] = {
                "status": "skipped",
                "reason": "database_url_not_configured",
                "tenant_id": tid,
            }
        return base

    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
            gates = fetch_tenant_modul_mate_gates(conn, tenant_id=tid)
    except Exception as exc:
        logger.warning("commercial_runtime_payload: tenant gates query failed: %s", exc)
        base["tenant_commercial"] = {
            "status": "error",
            "tenant_id": tid,
            "detail": str(exc)[:200],
        }
        return base

    if gates is None:
        base["tenant_commercial"] = {
            "status": "missing_row",
            "tenant_id": tid,
        }
        return base

    perms = order_placement_permissions(gates)
    base["tenant_commercial"] = {
        "status": "ok",
        "tenant_id": tid,
        "gates": asdict(gates),
        "can_place_demo_orders": perms.can_place_demo_orders,
        "can_place_live_orders": perms.can_place_live_orders,
        "commercial_execution_mode": perms.commercial_execution_mode.value,
    }
    return base
