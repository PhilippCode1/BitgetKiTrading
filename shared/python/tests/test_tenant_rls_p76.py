"""
P76: RLS-DoD — selbe Verbindung, zwei app.current_tenant_id, Ergebnis prüfen.
Benötigt Migration 628, app.usage_ledger, P76_RLS_TEST_DSN fuer DB-Test.
"""

from __future__ import annotations

import os

import pytest

from shared_py.postgres_tenant_rls import (
    apply_internal_all_tenants_rls_guc,
    apply_tenant_rls_guc,
)

def _p76_rls_dsn() -> str:
    """Nur P76_RLS_TEST_DSN (absichtlich), kein generisches DATABASE_URL in CI/Env."""
    return (os.environ.get("P76_RLS_TEST_DSN") or "").strip()


@pytest.mark.skipif(
    not _p76_rls_dsn(),
    reason="Setze P76_RLS_TEST_DSN=postgresql://… fuer RLS-Integrationstest (Migration 628).",
)
def test_rls_tenant_switches_in_one_connection() -> None:
    import psycopg
    from psycopg.rows import dict_row

    dsn = _p76_rls_dsn()

    t1 = f"p76rls_a_{os.getpid()}"[:32]
    t2 = f"p76rls_b_{os.getpid()}"[:32]
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        # Seed-Mandant + Ledger-Zeilen
        with conn.transaction():
            conn.execute("SELECT set_config('app.rls_internal_all_tenants', '1', true)")
            for tid in (t1, t2):
                conn.execute(
                    """
                    INSERT INTO app.tenant_commercial_state
                        (tenant_id, plan_id, budget_cap_usd_month)
                    VALUES (%s, 'starter', 100.0)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        plan_id = app.tenant_commercial_state.plan_id
                    """,
                    (tid,),
                )
        with conn.transaction():
            conn.execute("SELECT set_config('app.rls_internal_all_tenants', '1', true)")
            p = (t1, t2)
            conn.execute(
                "DELETE FROM app.usage_ledger "
                "WHERE tenant_id = ANY(%s::text[])",
                (p,),
            )
            ins = (
                """
                INSERT INTO app.usage_ledger (
                    tenant_id, event_type, quantity, unit,
                    line_total_list_usd, platform_markup_factor, meta_json
                )
                VALUES
                    (%s, 'p76_rls', 1, 'unit', 0, 1.0, '{}'),
                    (%s, 'p76_rls', 1, 'unit', 0, 1.0, '{}')
                """
            )
            conn.execute(ins, (t1, t2))

    with psycopg.connect(dsn, row_factory=dict_row) as conn2:
        apply_tenant_rls_guc(conn2, tenant_id=t1)
        rows = conn2.execute("SELECT * FROM app.trades").fetchall()  # noqa: S608
        tids1 = {str(r["tenant_id"]) for r in (rows or [])}  # type: ignore[union-attr, index, attr-defined]
        assert tids1 == {t1}, tids1
        q = "SELECT count(*)::bigint AS c FROM app.trades"
        n0 = int(conn2.execute(q).fetchone()["c"])  # type: ignore[index]
        apply_tenant_rls_guc(conn2, tenant_id=t2)
        n1 = int(conn2.execute(q).fetchone()["c"])  # type: ignore[index]
    assert n0 == 1 and n1 == 1

    with psycopg.connect(dsn, row_factory=dict_row) as c3:
        with c3.transaction():
            apply_internal_all_tenants_rls_guc(c3)
            ac2 = (t1, t2)
            del_ledger = (
                "DELETE FROM app.usage_ledger "
                "WHERE tenant_id = ANY(%s::text[])"
            )
            c3.execute(del_ledger, (ac2,))
            c3.execute(
                "DELETE FROM app.tenant_commercial_state "
                "WHERE tenant_id = ANY(%s::text[])",
                (ac2,),
            )


def test_tenant_redis_key_prefix() -> None:
    from shared_py.redis_client import (
        TenantNamespacedSyncRedis,
        build_tenant_redis_key,
        wrap_sync_redis_tenant,
    )

    class _Fake:
        def get(self, k: str) -> str:
            return f"got:{k}"

    ns = TenantNamespacedSyncRedis(_Fake(), "acme-1")
    assert ns.get("k") == "got:tenant:acme-1:k"
    assert build_tenant_redis_key("acme-1", "signal", "x") == "tenant:acme-1:signal/x"
    assert wrap_sync_redis_tenant(_Fake(), "t").k("z") == "tenant:t:z"
