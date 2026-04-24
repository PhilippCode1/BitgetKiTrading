"""
P76: Postgres-RLS-Gueltigkeitsvariable ``app.current_tenant_id`` (Mandantenisolation).

Nebenrolle: ``app.rls_internal_all_tenants=1`` nur in vertrauenswürdigem Plattform-/Admin-Code,
wenn bewusst die gesamte Mandanten-Tabelle sichtbar sein muss.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import psycopg

# Custom GUC-Präfix: siehe ``SHOW custom_variable_classes``; ``app.`` funktioniert
# bei ``SET [LOCAL]`` ohne vorherigen Eintrag in postgresql.conf.
GUC_TENANT_ID = "app.current_tenant_id"
GUC_INTERNAL_ALL = "app.rls_internal_all_tenants"


@runtime_checkable
class _ConnLike(Protocol):
    def execute(
        self, query: str, params: tuple[Any, ...] | None = None, **kw: Any
    ) -> Any: ...


def _set_config(
    conn: _ConnLike,
    key: str,
    value: str,
    *,
    is_local: bool = True,
) -> None:
    """
    Gegenüber ``SET name TO`` nutzt :func:`set_config` Werte mit ``%s`` sicher
    (Escaping) und klar trennbar in Transaktionen.
    """
    conn.execute("SELECT set_config(%s, %s, %s)", (key, value, is_local))


def apply_tenant_rls_guc(
    conn: psycopg.Connection[Any] | _ConnLike,
    *,
    tenant_id: str,
    is_local: bool = True,
) -> None:
    """
    Stellt pro Session/Transaktion den sichtbaren Mandanten ein (RLS-Policies in Migration 628).
    """
    tid = (tenant_id or "").strip()
    if not tid:
        return
    _set_config(
        conn,
        GUC_TENANT_ID,
        tid,
        is_local=is_local,
    )
    if is_local:
        _set_config(
            conn,
            GUC_INTERNAL_ALL,
            "",
            is_local=is_local,
        )


def apply_internal_all_tenants_rls_guc(
    conn: psycopg.Connection[Any] | _ConnLike, *, is_local: bool = True
) -> None:
    """
    NUR für abgesicherte Operator-/Internal-Routen: sichten aller ``tenant_id``-Zeilen.
    Löscht/überschreibt dabei bewusst die strikte Mandantengrenze.
    """
    _set_config(
        conn,
        GUC_INTERNAL_ALL,
        "1",
        is_local=is_local,
    )
