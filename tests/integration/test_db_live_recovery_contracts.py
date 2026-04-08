"""
DB-Recovery / Ops-Sicht: gleiche Queries wie Gateway-Ops (fetch_ops_summary).

Laueft in CI mit migrierter TEST_DATABASE_URL; saeubert Testzeilen deterministisch.
"""

from __future__ import annotations

import json
import uuid

import pytest
from api_gateway.db_ops_queries import fetch_ops_summary

pytestmark = [pytest.mark.integration, pytest.mark.stack_recovery]

_RECONCILE_MARKER = "integration_prompt35_reconcile"
_KILL_MARKER = "integration_prompt35_ks"


def test_ops_summary_reflects_reconcile_catch_up_drift_total(
    integration_postgres_conn,
) -> None:
    conn = integration_postgres_conn
    drift = {
        "total_count": 11,
        "order": {"local_only_count": 3, "exchange_only_count": 1},
        "positions": {"mismatch_count": 2},
        "snapshot_health": {"missing_count": 1, "stale_count": 0},
    }
    details = {"reason": _RECONCILE_MARKER, "drift": drift}

    try:
        conn.execute(
            """
            INSERT INTO live.reconcile_snapshots (
                status, runtime_mode, upstream_ok, shadow_enabled,
                live_submission_enabled, decision_counts_json, details_json
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                "degraded",
                "live",
                True,
                False,
                True,
                json.dumps({}),
                json.dumps(details),
            ),
        )
        conn.commit()

        summary = fetch_ops_summary(conn)
        lb = summary["live_broker"]
        assert lb["latest_reconcile_status"] == "degraded"
        assert int(lb["latest_reconcile_drift_total"]) == 11
    finally:
        conn.execute(
            "DELETE FROM live.reconcile_snapshots WHERE details_json->>'reason' = %s",
            (_RECONCILE_MARKER,),
        )
        conn.commit()


def test_reconcile_run_links_snapshot_and_completes(
    integration_postgres_conn,
) -> None:
    """FK live.reconcile_snapshots.reconcile_run_id + Abschluss des Laufs (Recovery-Persistenz)."""
    conn = integration_postgres_conn
    marker = "integration_prompt9_reconcile_chain"
    run_id: str | None = None
    try:
        cur = conn.execute(
            """
            INSERT INTO live.reconcile_runs (trigger_reason, meta_json, status)
            VALUES (%s, '{}'::jsonb, 'running')
            RETURNING reconcile_run_id
            """,
            (marker,),
        )
        row = cur.fetchone()
        assert row is not None
        run_id = str(row[0])
        details = {
            "reason": "integration_prompt9",
            "reconcile_run_id": run_id,
            "drift": {"total_count": 0},
            "recovery_state": {},
            "exchange_probe": {},
            "execution_controls": {},
        }
        cur2 = conn.execute(
            """
            INSERT INTO live.reconcile_snapshots (
                status, runtime_mode, upstream_ok, shadow_enabled,
                live_submission_enabled, decision_counts_json, details_json, reconcile_run_id
            ) VALUES ('ok', 'paper', true, false, false, '{}'::jsonb, %s::jsonb, %s::uuid)
            RETURNING reconcile_snapshot_id
            """,
            (json.dumps(details), run_id),
        )
        snap_row = cur2.fetchone()
        assert snap_row is not None
        snap_id = str(snap_row[0])

        conn.execute(
            """
            UPDATE live.reconcile_runs
            SET completed_ts = now(), status = 'completed',
                meta_json = meta_json || %s::jsonb
            WHERE reconcile_run_id = %s::uuid
            """,
            (json.dumps({"reconcile_snapshot_id": snap_id}), run_id),
        )
        conn.commit()

        chk = conn.execute(
            """
            SELECT r.status AS run_status, s.reconcile_snapshot_id::text AS sid
            FROM live.reconcile_runs r
            JOIN live.reconcile_snapshots s ON s.reconcile_run_id = r.reconcile_run_id
            WHERE r.trigger_reason = %s
            """,
            (marker,),
        ).fetchone()
        assert chk is not None
        assert chk[0] == "completed"
        assert chk[1] == snap_id
    finally:
        if run_id:
            conn.execute(
                "DELETE FROM live.reconcile_snapshots WHERE reconcile_run_id = %s::uuid",
                (run_id,),
            )
            conn.execute(
                "DELETE FROM live.reconcile_runs WHERE reconcile_run_id = %s::uuid",
                (run_id,),
            )
            conn.commit()


def test_ops_summary_kill_switch_active_count_matches_sql_semantics(
    integration_postgres_conn,
) -> None:
    conn = integration_postgres_conn
    sid = str(uuid.uuid4())
    try:
        summary0 = fetch_ops_summary(conn)
        base_ks = int(summary0["live_broker"]["active_kill_switch_count"])

        conn.execute(
            """
            INSERT INTO live.kill_switch_events (
                scope, scope_key, event_type, is_active, source, reason,
                symbol, product_type, margin_coin, internal_order_id, details_json
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, '{}'::jsonb)
            """,
            ("service", "service", "arm", True, "pytest", _KILL_MARKER + sid),
        )
        conn.commit()
        summary1 = fetch_ops_summary(conn)
        assert int(summary1["live_broker"]["active_kill_switch_count"]) == base_ks + 1

        conn.execute(
            """
            INSERT INTO live.kill_switch_events (
                scope, scope_key, event_type, is_active, source, reason,
                symbol, product_type, margin_coin, internal_order_id, details_json
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, '{}'::jsonb)
            """,
            ("service", "service", "release", False, "pytest", _KILL_MARKER + sid),
        )
        conn.commit()
        summary2 = fetch_ops_summary(conn)
        assert int(summary2["live_broker"]["active_kill_switch_count"]) == base_ks
    finally:
        conn.execute(
            "DELETE FROM live.kill_switch_events WHERE reason LIKE %s",
            (_KILL_MARKER + "%",),
        )
        conn.commit()


def test_ops_summary_safety_latch_reflects_latest_audit_action(
    integration_postgres_conn,
) -> None:
    conn = integration_postgres_conn
    marker = "integration_prompt35_latch"
    try:
        conn.execute(
            """
            INSERT INTO live.audit_trails (
                category, action, severity, scope, scope_key, source,
                internal_order_id, symbol, details_json
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s::jsonb)
            """,
            (
                "safety_latch",
                "arm",
                "critical",
                "service",
                "reconcile",
                "pytest",
                json.dumps({"reason": marker}),
            ),
        )
        conn.commit()
        assert fetch_ops_summary(conn)["live_broker"]["safety_latch_active"] is True

        conn.execute(
            """
            INSERT INTO live.audit_trails (
                category, action, severity, scope, scope_key, source,
                internal_order_id, symbol, details_json
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s::jsonb)
            """,
            (
                "safety_latch",
                "release",
                "info",
                "service",
                "reconcile",
                "pytest",
                json.dumps({"reason": marker}),
            ),
        )
        conn.commit()
        assert fetch_ops_summary(conn)["live_broker"]["safety_latch_active"] is False
    finally:
        conn.execute(
            """
            DELETE FROM live.audit_trails
            WHERE category = 'safety_latch'
              AND details_json->>'reason' = %s
            """,
            (marker,),
        )
        conn.commit()
