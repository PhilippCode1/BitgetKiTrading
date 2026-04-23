"""
Postgres-Ladelogik fuer Modul-Mate-Kommerzgates (tenant_modul_mate_gates).

Bezug: infra/migrations/postgres/604_modul_mate_execution_gates.sql
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row

from shared_py.commercial_contract_workflow import TenantContractStatus
from shared_py.product_policy import (
    CustomerCommercialGates,
    ExecutionPolicyViolationError,
    demo_trading_allowed,
    live_trading_allowed,
)


def fetch_tenant_modul_mate_gates(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
) -> CustomerCommercialGates | None:
    """
    Laedt Gates fuer einen Tenant oder None, wenn keine Zeile existiert.

    Spalten muessen zu CustomerCommercialGates passen (siehe Migration 604).
    Verbindung sollte row_factory=dict_row nutzen.
    """
    row = conn.execute(
        """
        SELECT trial_active, contract_accepted, admin_live_trading_granted,
               subscription_active, account_paused, account_suspended
        FROM app.tenant_modul_mate_gates
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    if not isinstance(row, Mapping):
        raise TypeError(
            "fetch_tenant_modul_mate_gates: psycopg Connection braucht row_factory=dict_row"
        )
    return CustomerCommercialGates(
        trial_active=bool(row["trial_active"]),
        contract_accepted=bool(row["contract_accepted"]),
        admin_live_trading_granted=bool(row["admin_live_trading_granted"]),
        subscription_active=bool(row["subscription_active"]),
        account_paused=bool(row["account_paused"]),
        account_suspended=bool(row["account_suspended"]),
    )


def fetch_tenant_modul_mate_gates_from_dsn(
    database_url: str,
    *,
    tenant_id: str,
    connect_timeout_sec: int = 5,
) -> CustomerCommercialGates | None:
    """Kurzform fuer Skripte (eigene kurze Verbindung)."""
    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=connect_timeout_sec,
    ) as conn:
        return fetch_tenant_modul_mate_gates(conn, tenant_id=tenant_id)


def tenant_has_active_live_commercial_contract(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
) -> bool:
    """
    True, wenn in app.tenant_contract (Migration 608, commercial_contract_workflow)
    ein abgeschlossener Vertrag mit Admin-Freigabe existiert.
    """
    status = TenantContractStatus.ADMIN_REVIEW_COMPLETE.value
    row = conn.execute(
        """
        SELECT 1
        FROM app.tenant_contract
        WHERE tenant_id = %s
          AND status = %s
        LIMIT 1
        """,
        (tenant_id, status),
    ).fetchone()
    return row is not None


def assert_execution_allowed(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    mode: str,
) -> bool:
    """
    Zentrales Live-/Demo-Execution-Gate: DB-tenant_modul_mate_gates *und* fuer LIVE
    ein activer commercial_contract_workflow (tenant_contract.admin_review_complete).

    Raises:
        ExecutionPolicyViolationError: Policy oder fehlender Vertrag fuer den Modus.

    Returns:
        True, wenn geprueft und erlaubt.
    """
    m = (mode or "").strip().upper()
    gates = fetch_tenant_modul_mate_gates(conn, tenant_id=tenant_id)
    if m == "LIVE":
        if gates is None:
            raise ExecutionPolicyViolationError(
                f"Kein app.tenant_modul_mate_gates Eintrag fuer tenant_id={tenant_id!r}",
                reason="tenant_modul_mate_gates_missing",
            )
        if not tenant_has_active_live_commercial_contract(conn, tenant_id=tenant_id):
            raise ExecutionPolicyViolationError(
                f"Kein abgeschlossener commercial_contract_workflow (LIVE) fuer "
                f"tenant_id={tenant_id!r}",
                reason="no_active_commercial_contract",
            )
        if not live_trading_allowed(gates):
            raise ExecutionPolicyViolationError(
                "Live-Handel laut product_policy/tenant_gates nicht erlaubt",
                reason="live_trading_not_permitted",
            )
        return True
    if m == "DEMO":
        if gates is None:
            raise ExecutionPolicyViolationError(
                f"Kein app.tenant_modul_mate_gates Eintrag fuer tenant_id={tenant_id!r}",
                reason="tenant_modul_mate_gates_missing",
            )
        if not demo_trading_allowed(gates):
            raise ExecutionPolicyViolationError(
                "Demo-Handel laut product_policy/tenant_gates nicht erlaubt",
                reason="demo_trading_not_permitted",
            )
        return True
    return True
