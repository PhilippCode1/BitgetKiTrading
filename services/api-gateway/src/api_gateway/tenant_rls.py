"""P76: Einheitliches Oeffnen von Psycopg-Connections mit RLS-GUC (Mandant / Internal)."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from shared_py.postgres_tenant_rls import (
    apply_internal_all_tenants_rls_guc,
    apply_tenant_rls_guc,
)


@contextmanager
def gateway_psycopg(
    dsn: str,
    *,
    connect_timeout: int = 5,
    row_factory: Any = dict_row,
    tenant_id: str | None = None,
    rls_internal_read_all: bool = False,
) -> Generator[psycopg.Connection[Any], None, None]:
    """
    RLS: pro Request ``tenant_id`` setzen, oder (sparsam) alles-mandantig fuer Operator.
    Unbenannt/ohne RLS-Angabe: keine Aenderung (nur Pfade ohne tenant_id-Tabellen nutzen).
    """
    with psycopg.connect(
        dsn,
        row_factory=row_factory,
        connect_timeout=connect_timeout,
    ) as conn:
        if rls_internal_read_all:
            apply_internal_all_tenants_rls_guc(conn)
        elif (tenant_id or "").strip():
            apply_tenant_rls_guc(conn, tenant_id=str(tenant_id).strip())
        yield conn
