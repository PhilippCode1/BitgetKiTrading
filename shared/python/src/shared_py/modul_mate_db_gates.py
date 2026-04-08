"""
Postgres-Ladelogik fuer Modul-Mate-Kommerzgates (tenant_modul_mate_gates).

Bezug: infra/migrations/postgres/604_modul_mate_execution_gates.sql
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row

from shared_py.product_policy import CustomerCommercialGates


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
