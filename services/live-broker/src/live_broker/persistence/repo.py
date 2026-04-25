from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

try:
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - Laufzeit nutzt psycopg[pool]
    ConnectionPool = None  # type: ignore[assignment, misc]

from shared_py.datastore.pool_config import (
    PSYCOPG_POOL_MAX_LIFETIME_SEC,
    PSYCOPG_POOL_MAX_SIZE,
)

logger = logging.getLogger("live_broker.repo")

_REQUIRED_TABLES = (
    "live.execution_decisions",
    "live.orders",
    "live.order_actions",
    "live.exit_plans",
    "live.fills",
    "live.exchange_snapshots",
    "live.positions",
    "live.kill_switch_events",
    "live.audit_trails",
    "live.paper_reference_events",
    "live.reconcile_snapshots",
    "live.reconcile_runs",
    "live.shadow_live_assessments",
    "live.execution_risk_snapshots",
    "live.execution_journal",
    "live.execution_operator_releases",
)
_TERMINAL_ORDER_STATUSES = {
    "canceled",
    "filled",
    "error",
    "replaced",
    "flattened",
    "flatten_failed",
    "timed_out",
}
_KILL_SWITCH_STATE_EVENT_TYPES = ("arm", "release")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return value
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in row.items()}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


class LiveBrokerRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any = None
        _use = (os.environ.get("BITGET_USE_PSYCOPG_POOL", "1") or "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
            "",
        )
        if (
            _use
            and dsn.strip()
            and ConnectionPool is not None
        ):
            self._pool = ConnectionPool(
                dsn.strip(),
                min_size=1,
                max_size=PSYCOPG_POOL_MAX_SIZE,
                max_lifetime=float(PSYCOPG_POOL_MAX_LIFETIME_SEC),
            )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def schema_ready(self) -> tuple[bool, str]:
        query = """
        SELECT
            to_regclass('live.execution_decisions') IS NOT NULL AS execution_decisions,
            to_regclass('live.orders') IS NOT NULL AS orders,
            to_regclass('live.order_actions') IS NOT NULL AS order_actions,
            to_regclass('live.exit_plans') IS NOT NULL AS exit_plans,
            to_regclass('live.fills') IS NOT NULL AS fills,
            to_regclass('live.exchange_snapshots') IS NOT NULL AS exchange_snapshots,
            to_regclass('live.positions') IS NOT NULL AS positions,
            to_regclass('live.kill_switch_events') IS NOT NULL AS kill_switch_events,
            to_regclass('live.audit_trails') IS NOT NULL AS audit_trails,
            to_regclass('live.paper_reference_events') IS NOT NULL AS paper_reference_events,
            to_regclass('live.reconcile_snapshots') IS NOT NULL AS reconcile_snapshots,
            to_regclass('live.reconcile_runs') IS NOT NULL AS reconcile_runs,
            to_regclass('live.shadow_live_assessments') IS NOT NULL AS shadow_live_assessments,
            to_regclass('live.execution_risk_snapshots') IS NOT NULL AS execution_risk_snapshots,
            to_regclass('live.execution_journal') IS NOT NULL AS execution_journal,
            to_regclass('live.execution_operator_releases') IS NOT NULL AS execution_operator_releases
        """
        try:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query)
                    row = cur.fetchone()
        except Exception as exc:
            return False, str(exc)[:200]
        if row is None:
            return False, "schema_query_failed"
        missing = [name for name in _REQUIRED_TABLES if not row[name.split(".")[1]]]
        if missing:
            return False, f"missing_tables={missing}"
        return True, "ok"

    def fetch_online_drift_state(self) -> dict[str, Any] | None:
        sql = """
        SELECT effective_action, computed_at, lookback_minutes, breakdown_json
        FROM learn.online_drift_state
        WHERE scope = 'global'
        LIMIT 1
        """
        try:
            with self._connect() as conn:
                row = conn.execute(sql).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        data = dict(row)
        ts = data.get("computed_at")
        if ts is not None and hasattr(ts, "isoformat"):
            data["computed_at"] = ts.isoformat()
        return data

    def record_execution_decision(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.execution_decisions (
                    execution_id,
                    source_service,
                    source_signal_id,
                    symbol,
                    timeframe,
                    direction,
                    requested_runtime_mode,
                    effective_runtime_mode,
                    decision_action,
                    decision_reason,
                    order_type,
                    leverage,
                    approved_7x,
                    qty_base,
                    entry_price,
                    stop_loss,
                    take_profit,
                    payload_json,
                    trace_json
                ) VALUES (
                    COALESCE(%(execution_id)s::uuid, gen_random_uuid()),
                    %(source_service)s,
                    %(source_signal_id)s,
                    %(symbol)s,
                    %(timeframe)s,
                    %(direction)s,
                    %(requested_runtime_mode)s,
                    %(effective_runtime_mode)s,
                    %(decision_action)s,
                    %(decision_reason)s,
                    %(order_type)s,
                    %(leverage)s,
                    %(approved_7x)s,
                    %(qty_base)s,
                    %(entry_price)s,
                    %(stop_loss)s,
                    %(take_profit)s,
                    %(payload_json)s,
                    %(trace_json)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "execution_id": record.get("execution_id"),
                    "payload_json": Json(_json_safe(record.get("payload_json", {}))),
                    "trace_json": Json(_json_safe(record.get("trace_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("execution decision insert failed")
        return _serialize_row(dict(row))

    def get_execution_decision(self, execution_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.execution_decisions
                WHERE execution_id = %s
                """,
                (execution_id,),
            ).fetchone()
        return _serialize_row(dict(row)) if row is not None else None

    def record_operator_release(
        self,
        *,
        execution_id: str,
        source: str = "internal-api",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.execution_operator_releases (
                    execution_id,
                    source,
                    details_json
                ) VALUES (
                    %(execution_id)s,
                    %(source)s,
                    %(details_json)s
                )
                ON CONFLICT (execution_id) DO UPDATE SET
                    released_ts = now(),
                    source = EXCLUDED.source,
                    details_json = EXCLUDED.details_json
                RETURNING *
                """,
                {
                    "execution_id": execution_id,
                    "source": source,
                    "details_json": Json(_json_safe(details or {})),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("operator release upsert failed")
        return _serialize_row(dict(row))

    def get_operator_release(self, execution_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.execution_operator_releases
                WHERE execution_id = %s
                """,
                (execution_id,),
            ).fetchone()
        return _serialize_row(dict(row)) if row is not None else None

    def record_execution_journal(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.execution_journal (
                    execution_decision_id,
                    internal_order_id,
                    phase,
                    details_json
                ) VALUES (
                    %(execution_decision_id)s,
                    %(internal_order_id)s,
                    %(phase)s,
                    %(details_json)s
                )
                RETURNING *
                """,
                {
                    "execution_decision_id": record.get("execution_decision_id"),
                    "internal_order_id": record.get("internal_order_id"),
                    "phase": record["phase"],
                    "details_json": Json(_json_safe(record.get("details_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("execution journal insert failed")
        return _serialize_row(dict(row))

    def list_execution_journal_for_execution(
        self,
        execution_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(500, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.execution_journal
                WHERE execution_decision_id = %s
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (execution_id, lim),
            ).fetchall()
        return [_serialize_row(dict(r)) for r in rows]

    def list_recent_execution_journal(self, limit: int = 200) -> list[dict[str, Any]]:
        lim = max(1, min(1000, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT journal_id, execution_decision_id, internal_order_id, phase, created_ts
                FROM live.execution_journal
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (lim,),
            ).fetchall()
        return [_serialize_row(dict(r)) for r in rows]

    def record_execution_risk_snapshot(
        self,
        execution_decision_id: str,
        risk_decision: dict[str, Any],
    ) -> None:
        detail = _json_safe(risk_decision)
        metrics = detail.get("metrics") if isinstance(detail.get("metrics"), dict) else {}
        reasons = detail.get("reasons_json") if isinstance(detail.get("reasons_json"), list) else []
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live.execution_risk_snapshots (
                    execution_decision_id,
                    trade_action,
                    decision_state,
                    primary_reason,
                    reasons_json,
                    metrics_json,
                    detail_json
                ) VALUES (
                    %(execution_decision_id)s,
                    %(trade_action)s,
                    %(decision_state)s,
                    %(primary_reason)s,
                    %(reasons_json)s,
                    %(metrics_json)s,
                    %(detail_json)s
                )
                ON CONFLICT (execution_decision_id) DO NOTHING
                """,
                {
                    "execution_decision_id": execution_decision_id,
                    "trade_action": risk_decision.get("trade_action"),
                    "decision_state": risk_decision.get("decision_state"),
                    "primary_reason": risk_decision.get("decision_reason"),
                    "reasons_json": Json(_json_safe(reasons)),
                    "metrics_json": Json(_json_safe(metrics)),
                    "detail_json": Json(detail),
                },
            )

    def record_shadow_live_assessment(
        self,
        *,
        execution_decision_id: str,
        source_signal_id: str | None,
        symbol: str,
        match_ok: bool,
        gate_blocked: bool,
        report: dict[str, Any],
    ) -> None:
        protocol_version = report.get("protocol_version") if isinstance(report, dict) else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO live.shadow_live_assessments (
                    execution_decision_id,
                    source_signal_id,
                    symbol,
                    match_ok,
                    gate_blocked,
                    protocol_version,
                    report_json
                ) VALUES (
                    %(execution_decision_id)s,
                    %(source_signal_id)s,
                    %(symbol)s,
                    %(match_ok)s,
                    %(gate_blocked)s,
                    %(protocol_version)s,
                    %(report_json)s
                )
                ON CONFLICT (execution_decision_id) DO NOTHING
                """,
                {
                    "execution_decision_id": execution_decision_id,
                    "source_signal_id": source_signal_id,
                    "symbol": symbol,
                    "match_ok": match_ok,
                    "gate_blocked": gate_blocked,
                    "protocol_version": protocol_version,
                    "report_json": Json(_json_safe(report)),
                },
            )

    def begin_reconcile_run(
        self,
        trigger_reason: str,
        meta_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.reconcile_runs (trigger_reason, meta_json)
                VALUES (%(trigger_reason)s, %(meta_json)s)
                RETURNING *
                """,
                {
                    "trigger_reason": trigger_reason,
                    "meta_json": Json(_json_safe(meta_json or {})),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("reconcile run insert failed")
        return _serialize_row(dict(row))

    def complete_reconcile_run(
        self,
        reconcile_run_id: str,
        status: str,
        meta_patch: dict[str, Any] | None = None,
    ) -> None:
        patch = _json_safe(meta_patch or {})
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE live.reconcile_runs
                SET completed_ts = now(),
                    status = %(status)s,
                    meta_json = meta_json || %(meta_patch)s::jsonb
                WHERE reconcile_run_id = %(reconcile_run_id)s
                """,
                {
                    "status": status,
                    "meta_patch": Json(patch),
                    "reconcile_run_id": reconcile_run_id,
                },
            )

    def list_recent_execution_decisions(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.execution_decisions
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def decision_action_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT decision_action, count(*) AS total
                FROM live.execution_decisions
                GROUP BY decision_action
                """
            ).fetchall()
        return {str(row["decision_action"]): int(row["total"]) for row in rows}

    def upsert_order(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.orders (
                    internal_order_id,
                    parent_internal_order_id,
                    source_service,
                    symbol,
                    product_type,
                    margin_mode,
                    margin_coin,
                    market_family,
                    margin_account_mode,
                    source_execution_decision_id,
                    side,
                    trade_side,
                    order_type,
                    force,
                    reduce_only,
                    size,
                    price,
                    note,
                    client_oid,
                    exchange_order_id,
                    status,
                    last_action,
                    last_http_status,
                    last_exchange_code,
                    last_exchange_msg,
                    last_response_json,
                    trace_json
                ) VALUES (
                    %(internal_order_id)s,
                    %(parent_internal_order_id)s,
                    %(source_service)s,
                    %(symbol)s,
                    %(product_type)s,
                    %(margin_mode)s,
                    %(margin_coin)s,
                    %(market_family)s,
                    %(margin_account_mode)s,
                    %(source_execution_decision_id)s,
                    %(side)s,
                    %(trade_side)s,
                    %(order_type)s,
                    %(force)s,
                    %(reduce_only)s,
                    %(size)s,
                    %(price)s,
                    %(note)s,
                    %(client_oid)s,
                    %(exchange_order_id)s,
                    %(status)s,
                    %(last_action)s,
                    %(last_http_status)s,
                    %(last_exchange_code)s,
                    %(last_exchange_msg)s,
                    %(last_response_json)s,
                    %(trace_json)s
                )
                ON CONFLICT (internal_order_id) DO UPDATE SET
                    parent_internal_order_id = EXCLUDED.parent_internal_order_id,
                    source_service = EXCLUDED.source_service,
                    symbol = EXCLUDED.symbol,
                    product_type = EXCLUDED.product_type,
                    margin_mode = EXCLUDED.margin_mode,
                    margin_coin = EXCLUDED.margin_coin,
                    market_family = COALESCE(EXCLUDED.market_family, live.orders.market_family),
                    margin_account_mode = COALESCE(
                        EXCLUDED.margin_account_mode, live.orders.margin_account_mode
                    ),
                    source_execution_decision_id = COALESCE(
                        EXCLUDED.source_execution_decision_id,
                        live.orders.source_execution_decision_id
                    ),
                    side = EXCLUDED.side,
                    trade_side = EXCLUDED.trade_side,
                    order_type = EXCLUDED.order_type,
                    force = EXCLUDED.force,
                    reduce_only = EXCLUDED.reduce_only,
                    size = EXCLUDED.size,
                    price = EXCLUDED.price,
                    note = EXCLUDED.note,
                    client_oid = EXCLUDED.client_oid,
                    exchange_order_id = EXCLUDED.exchange_order_id,
                    status = EXCLUDED.status,
                    last_action = EXCLUDED.last_action,
                    last_http_status = EXCLUDED.last_http_status,
                    last_exchange_code = EXCLUDED.last_exchange_code,
                    last_exchange_msg = EXCLUDED.last_exchange_msg,
                    last_response_json = EXCLUDED.last_response_json,
                    trace_json = EXCLUDED.trace_json,
                    updated_ts = now()
                RETURNING *
                """,
                {
                    **record,
                    "last_response_json": Json(
                        _json_safe(record.get("last_response_json", {}))
                    ),
                    "trace_json": Json(_json_safe(record.get("trace_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("order upsert failed")
        return _serialize_row(dict(row))

    def upsert_exit_plan(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.exit_plans (
                    plan_id,
                    root_internal_order_id,
                    source_signal_id,
                    symbol,
                    side,
                    timeframe,
                    state,
                    entry_price,
                    initial_qty,
                    remaining_qty,
                    stop_plan_json,
                    tp_plan_json,
                    context_json,
                    last_market_json,
                    last_decision_json,
                    last_reason,
                    closed_ts
                ) VALUES (
                    COALESCE(%(plan_id)s, gen_random_uuid()),
                    %(root_internal_order_id)s,
                    %(source_signal_id)s,
                    %(symbol)s,
                    %(side)s,
                    %(timeframe)s,
                    %(state)s,
                    %(entry_price)s,
                    %(initial_qty)s,
                    %(remaining_qty)s,
                    %(stop_plan_json)s,
                    %(tp_plan_json)s,
                    %(context_json)s,
                    %(last_market_json)s,
                    %(last_decision_json)s,
                    %(last_reason)s,
                    %(closed_ts)s
                )
                ON CONFLICT (root_internal_order_id) DO UPDATE SET
                    source_signal_id = EXCLUDED.source_signal_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    timeframe = EXCLUDED.timeframe,
                    state = EXCLUDED.state,
                    entry_price = EXCLUDED.entry_price,
                    initial_qty = EXCLUDED.initial_qty,
                    remaining_qty = EXCLUDED.remaining_qty,
                    stop_plan_json = EXCLUDED.stop_plan_json,
                    tp_plan_json = EXCLUDED.tp_plan_json,
                    context_json = EXCLUDED.context_json,
                    last_market_json = EXCLUDED.last_market_json,
                    last_decision_json = EXCLUDED.last_decision_json,
                    last_reason = EXCLUDED.last_reason,
                    closed_ts = EXCLUDED.closed_ts,
                    updated_ts = now()
                RETURNING *
                """,
                {
                    **record,
                    "stop_plan_json": Json(_json_safe(record.get("stop_plan_json", {}))),
                    "tp_plan_json": Json(_json_safe(record.get("tp_plan_json", {}))),
                    "context_json": Json(_json_safe(record.get("context_json", {}))),
                    "last_market_json": Json(_json_safe(record.get("last_market_json", {}))),
                    "last_decision_json": Json(_json_safe(record.get("last_decision_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("exit plan upsert failed")
        return _serialize_row(dict(row))

    def get_exit_plan_by_root_order(self, root_internal_order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.exit_plans
                WHERE root_internal_order_id = %s
                """,
                (root_internal_order_id,),
            ).fetchone()
        return _serialize_row(dict(row)) if row is not None else None

    def list_active_exit_plans(
        self,
        *,
        limit: int = 200,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        where = ["state IN ('pending', 'active', 'closing')"]
        params: list[Any] = []
        if symbol is not None:
            where.append("symbol = %s")
            params.append(symbol)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM live.exit_plans
                WHERE {' AND '.join(where)}
                ORDER BY updated_ts ASC
                LIMIT %s
                """,
                tuple(params),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def get_order_by_internal_id(self, internal_order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.orders
                WHERE internal_order_id = %s
                """,
                (internal_order_id,),
            ).fetchone()
        if row is None:
            return None
        return _serialize_row(dict(row))

    def get_order_by_client_oid(self, client_oid: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.orders
                WHERE client_oid = %s
                """,
                (client_oid,),
            ).fetchone()
        if row is None:
            return None
        return _serialize_row(dict(row))

    def get_order_by_exchange_order_id(self, exchange_order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.orders
                WHERE exchange_order_id = %s
                """,
                (exchange_order_id,),
            ).fetchone()
        if row is None:
            return None
        return _serialize_row(dict(row))

    def list_recent_orders(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.orders
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def list_active_orders(
        self,
        *,
        limit: int = 200,
        symbol: str | None = None,
        product_type: str | None = None,
        internal_order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["NOT (LOWER(COALESCE(status, '')) = ANY(%s))"]
        params: list[Any] = [sorted(_TERMINAL_ORDER_STATUSES)]
        if symbol:
            clauses.append("symbol = %s")
            params.append(symbol)
        if product_type:
            clauses.append("product_type = %s")
            params.append(product_type)
        if internal_order_id:
            clauses.append("internal_order_id = %s")
            params.append(internal_order_id)
        params.append(limit)
        where_clause = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM live.orders
                WHERE {where_clause}
                ORDER BY COALESCE(updated_ts, created_ts) DESC, created_ts DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def order_status_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, count(*) AS total
                FROM live.orders
                GROUP BY status
                """
            ).fetchall()
        return {str(row["status"]): int(row["total"]) for row in rows}

    def record_order_action(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.order_actions (
                    internal_order_id,
                    action,
                    request_path,
                    client_oid,
                    exchange_order_id,
                    http_status,
                    exchange_code,
                    exchange_msg,
                    retry_count,
                    request_json,
                    response_json
                ) VALUES (
                    %(internal_order_id)s,
                    %(action)s,
                    %(request_path)s,
                    %(client_oid)s,
                    %(exchange_order_id)s,
                    %(http_status)s,
                    %(exchange_code)s,
                    %(exchange_msg)s,
                    %(retry_count)s,
                    %(request_json)s,
                    %(response_json)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "request_json": Json(_json_safe(record.get("request_json", {}))),
                    "response_json": Json(_json_safe(record.get("response_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("order action insert failed")
        return _serialize_row(dict(row))

    def list_recent_order_actions(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.order_actions
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def record_fill(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.fills (
                    internal_order_id,
                    exchange_order_id,
                    exchange_trade_id,
                    symbol,
                    side,
                    price,
                    size,
                    fee,
                    fee_coin,
                    is_maker,
                    exchange_ts_ms,
                    ingest_source,
                    raw_json
                ) VALUES (
                    %(internal_order_id)s,
                    %(exchange_order_id)s,
                    %(exchange_trade_id)s,
                    %(symbol)s,
                    %(side)s,
                    %(price)s,
                    %(size)s,
                    %(fee)s,
                    %(fee_coin)s,
                    %(is_maker)s,
                    %(exchange_ts_ms)s,
                    %(ingest_source)s,
                    %(raw_json)s
                )
                ON CONFLICT (exchange_trade_id) DO UPDATE SET
                    internal_order_id = EXCLUDED.internal_order_id,
                    exchange_order_id = EXCLUDED.exchange_order_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    price = EXCLUDED.price,
                    size = EXCLUDED.size,
                    fee = EXCLUDED.fee,
                    fee_coin = EXCLUDED.fee_coin,
                    is_maker = EXCLUDED.is_maker,
                    exchange_ts_ms = EXCLUDED.exchange_ts_ms,
                    ingest_source = EXCLUDED.ingest_source,
                    raw_json = EXCLUDED.raw_json
                RETURNING *
                """,
                {
                    **record,
                    "ingest_source": record.get("ingest_source") or "exchange",
                    "raw_json": Json(_json_safe(record.get("raw_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("fill insert failed")
        return _serialize_row(dict(row))

    def list_recent_fills(
        self,
        limit: int,
        *,
        symbol: str | None = None,
        internal_order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = %s")
            params.append(symbol)
        if internal_order_id:
            clauses.append("internal_order_id = %s")
            params.append(internal_order_id)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM live.fills
                {where_clause}
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def record_exchange_snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.exchange_snapshots (
                    reconcile_run_id,
                    symbol,
                    snapshot_type,
                    raw_data
                ) VALUES (
                    %(reconcile_run_id)s,
                    %(symbol)s,
                    %(snapshot_type)s,
                    %(raw_data)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "raw_data": Json(_json_safe(record.get("raw_data", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("exchange snapshot insert failed")
        return _serialize_row(dict(row))

    def list_latest_exchange_snapshots(
        self,
        snapshot_type: str,
        *,
        symbol: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [snapshot_type]
        symbol_clause = ""
        if symbol is not None:
            symbol_clause = "AND symbol = %s"
            params.append(symbol)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM (
                    SELECT DISTINCT ON (snapshot_type, symbol) *
                    FROM live.exchange_snapshots
                    WHERE snapshot_type = %s
                    {symbol_clause}
                    ORDER BY snapshot_type, symbol, created_ts DESC
                ) snapshots
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def list_exchange_snapshots_since(
        self,
        snapshot_type: str,
        *,
        since_ts_ms: int,
        symbol: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [snapshot_type, float(since_ts_ms) / 1000.0]
        symbol_clause = ""
        if symbol is not None:
            symbol_clause = "AND symbol = %s"
            params.append(symbol)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM live.exchange_snapshots
                WHERE snapshot_type = %s
                  AND created_ts >= to_timestamp(%s)
                  {symbol_clause}
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                tuple(params),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def reconstruct_runtime_state(
        self,
        *,
        order_limit: int = 500,
        fill_limit: int = 500,
        journal_limit: int = 200,
        exit_plan_limit: int = 200,
    ) -> dict[str, Any]:
        open_orders = self.list_active_orders(limit=order_limit)
        order_snapshots = self.list_latest_exchange_snapshots("orders", limit=order_limit)
        position_snapshots = self.list_latest_exchange_snapshots("positions", limit=order_limit)
        account_snapshots = self.list_latest_exchange_snapshots("account", limit=order_limit)
        recent_fills = self.list_recent_fills(fill_limit)
        journal_recent = self.list_recent_execution_journal(journal_limit)
        exit_plans = self.list_active_exit_plans(limit=exit_plan_limit)
        by_state: dict[str, int] = {}
        for plan in exit_plans:
            st = str(plan.get("state") or "unknown")
            by_state[st] = by_state.get(st, 0) + 1
        return {
            "open_orders": open_orders,
            "exchange_order_snapshots": order_snapshots,
            "exchange_position_snapshots": position_snapshots,
            "exchange_account_snapshots": account_snapshots,
            "recent_fills": recent_fills,
            "execution_journal_recent": journal_recent,
            "active_exit_plans": exit_plans,
            "active_exit_plans_summary": {
                "total": len(exit_plans),
                "by_state": by_state,
            },
            "open_order_count": len(open_orders),
            "exchange_order_snapshot_count": len(order_snapshots),
            "exchange_position_snapshot_count": len(position_snapshots),
            "exchange_account_snapshot_count": len(account_snapshots),
            "recent_fill_count": len(recent_fills),
            "execution_journal_recent_count": len(journal_recent),
        }

    def record_kill_switch_event(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.kill_switch_events (
                    scope,
                    scope_key,
                    event_type,
                    is_active,
                    source,
                    reason,
                    symbol,
                    product_type,
                    margin_coin,
                    internal_order_id,
                    details_json
                ) VALUES (
                    %(scope)s,
                    %(scope_key)s,
                    %(event_type)s,
                    %(is_active)s,
                    %(source)s,
                    %(reason)s,
                    %(symbol)s,
                    %(product_type)s,
                    %(margin_coin)s,
                    %(internal_order_id)s,
                    %(details_json)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "details_json": Json(_json_safe(record.get("details_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("kill switch event insert failed")
        return _serialize_row(dict(row))

    def list_recent_kill_switch_events(
        self,
        limit: int,
        *,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        if active_only:
            return self.active_kill_switches()[:limit]
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.kill_switch_events
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def active_kill_switches(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (scope, scope_key) *
                FROM live.kill_switch_events
                WHERE event_type = ANY(%s)
                ORDER BY scope, scope_key, created_ts DESC
                """,
                (list(_KILL_SWITCH_STATE_EVENT_TYPES),),
            ).fetchall()
        return [
            item
            for item in (_serialize_row(dict(row)) for row in rows)
            if bool(item.get("is_active"))
        ]

    def record_audit_trail(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.audit_trails (
                    category,
                    action,
                    severity,
                    scope,
                    scope_key,
                    source,
                    internal_order_id,
                    symbol,
                    details_json
                ) VALUES (
                    %(category)s,
                    %(action)s,
                    %(severity)s,
                    %(scope)s,
                    %(scope_key)s,
                    %(source)s,
                    %(internal_order_id)s,
                    %(symbol)s,
                    %(details_json)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "details_json": Json(_json_safe(record.get("details_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("audit trail insert failed")
        return _serialize_row(dict(row))

    def safety_latch_is_active(self) -> bool:
        """True wenn letztes safety_latch-Audit `arm` ist (blockt Live-Fire bis operatorisches release)."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT action
                FROM live.audit_trails
                WHERE category = 'safety_latch'
                ORDER BY created_ts DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return False
        return str(dict(row).get("action") or "") == "arm"

    def list_recent_audit_trails(
        self,
        limit: int,
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM live.audit_trails
                    WHERE category = %s
                    ORDER BY created_ts DESC
                    LIMIT %s
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM live.audit_trails
                    ORDER BY created_ts DESC
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def record_paper_reference_event(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.paper_reference_events (
                    source_message_id,
                    dedupe_key,
                    event_type,
                    position_id,
                    symbol,
                    state,
                    qty_base,
                    reason,
                    payload_json,
                    trace_json
                ) VALUES (
                    %(source_message_id)s,
                    %(dedupe_key)s,
                    %(event_type)s,
                    %(position_id)s,
                    %(symbol)s,
                    %(state)s,
                    %(qty_base)s,
                    %(reason)s,
                    %(payload_json)s,
                    %(trace_json)s
                )
                ON CONFLICT (dedupe_key) DO UPDATE SET
                    state = EXCLUDED.state,
                    qty_base = EXCLUDED.qty_base,
                    reason = EXCLUDED.reason,
                    payload_json = EXCLUDED.payload_json,
                    trace_json = EXCLUDED.trace_json,
                    updated_ts = now()
                RETURNING *
                """,
                {
                    **record,
                    "payload_json": Json(_json_safe(record.get("payload_json", {}))),
                    "trace_json": Json(_json_safe(record.get("trace_json", {}))),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("paper reference insert failed")
        return _serialize_row(dict(row))

    def list_recent_paper_reference_events(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.paper_reference_events
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_serialize_row(dict(row)) for row in rows]

    def record_reconcile_snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO live.reconcile_snapshots (
                    status,
                    runtime_mode,
                    upstream_ok,
                    shadow_enabled,
                    live_submission_enabled,
                    decision_counts_json,
                    details_json,
                    reconcile_run_id
                ) VALUES (
                    %(status)s,
                    %(runtime_mode)s,
                    %(upstream_ok)s,
                    %(shadow_enabled)s,
                    %(live_submission_enabled)s,
                    %(decision_counts_json)s,
                    %(details_json)s,
                    %(reconcile_run_id)s
                )
                RETURNING *
                """,
                {
                    **record,
                    "decision_counts_json": Json(
                        _json_safe(record.get("decision_counts_json", {}))
                    ),
                    "details_json": Json(_json_safe(record.get("details_json", {}))),
                    "reconcile_run_id": record.get("reconcile_run_id"),
                },
            ).fetchone()
        if row is None:
            raise RuntimeError("reconcile snapshot insert failed")
        return _serialize_row(dict(row))

    def latest_reconcile_snapshot(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM live.reconcile_snapshots
                ORDER BY created_ts DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return _serialize_row(dict(row))

    def runtime_summary(self) -> dict[str, Any]:
        return {
            "schema_ready": self.schema_ready()[0],
            "decision_counts": self.decision_action_counts(),
            "order_status_counts": self.order_status_counts(),
            "recent_fills": self.list_recent_fills(20),
            "active_kill_switches": self.active_kill_switches(),
            "latest_reconcile": self.latest_reconcile_snapshot(),
            "recovery_state": self.reconstruct_runtime_state(order_limit=100, fill_limit=100),
        }

    def list_live_positions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM live.positions
                ORDER BY inst_id, hold_side, product_type
                """
            ).fetchall()
        return [_serialize_row(dict(r)) for r in rows]

    def delete_live_position(self, inst_id: str, product_type: str, hold_side: str) -> bool:
        with self._connect() as conn:
            r = conn.execute(
                """
                DELETE FROM live.positions
                WHERE inst_id = %s AND product_type = %s AND hold_side = %s
                """,
                (inst_id.strip().upper(), product_type.strip().upper(), hold_side.strip().lower()),
            )
            return (r.rowcount or 0) > 0

    def upsert_live_position_from_bitget(
        self,
        row: dict[str, Any],
        *,
        notional_value: Any,
    ) -> dict[str, Any]:
        """Merge aus Bitget-REST/WS-Positionsobjekt (Futures/linear)."""
        raw = row.get("raw_json") or {}
        if not isinstance(raw, dict):
            raw = {}
        size = raw.get("total")
        if size in (None, ""):
            size = raw.get("available")
        entry = raw.get("openPriceAvg") or raw.get("openAvgPrice")
        margin = raw.get("margin") or raw.get("marginSize")
        inst = str(row.get("inst_id") or "").strip().upper()
        ptype = str(row.get("product_type") or "").strip().upper()
        hside = str(row.get("hold_side") or "").strip().lower()
        src = str(row.get("source") or "reconcile_shadow_sync")
        nvl = notional_value
        if nvl is not None and not isinstance(nvl, Decimal):
            nvl = Decimal(str(nvl))
        with self._connect() as conn:
            r = conn.execute(
                """
                INSERT INTO live.positions (
                    inst_id, product_type, hold_side, size_base, entry_price, margin, notional_value, raw_json, source
                ) VALUES (
                    %(inst_id)s, %(product_type)s, %(hold_side)s, %(size_base)s, %(entry_price)s, %(margin)s, %(notional_value)s, %(raw_json)s, %(source)s
                )
                ON CONFLICT (inst_id, product_type, hold_side) DO UPDATE SET
                    size_base = EXCLUDED.size_base,
                    entry_price = EXCLUDED.entry_price,
                    margin = EXCLUDED.margin,
                    notional_value = EXCLUDED.notional_value,
                    raw_json = EXCLUDED.raw_json,
                    source = EXCLUDED.source,
                    updated_ts = now()
                RETURNING *
                """,
                {
                    "inst_id": inst,
                    "product_type": ptype,
                    "hold_side": hside,
                    "size_base": size,
                    "entry_price": entry,
                    "margin": margin,
                    "notional_value": nvl,
                    "raw_json": Json(_json_safe(raw)),
                    "source": src,
                },
            ).fetchone()
        if r is None:
            raise RuntimeError("live.positions upsert failed")
        return _serialize_row(dict(r))

    def upsert_apex_latency_audit(
        self,
        *,
        signal_id: str,
        execution_id: str | None,
        apex_trace: dict[str, Any],
    ) -> None:
        """Prompt 39: `app.apex_latency_audit` (kein starker Contract mit audit-ledger HTTP)."""
        if not (signal_id or "").strip() or not isinstance(apex_trace, dict) or not apex_trace:
            return
        eid: UUID | None
        try:
            eid = UUID(str(execution_id)) if execution_id else None
        except (TypeError, ValueError):
            eid = None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app.apex_latency_audit (signal_id, execution_id, trace_id, apex_trace, updated_at)
                VALUES (%(sid)s, %(eid)s, %(tid)s, %(apex)s, now())
                ON CONFLICT (signal_id) DO UPDATE SET
                    execution_id = COALESCE(EXCLUDED.execution_id, app.apex_latency_audit.execution_id),
                    trace_id = EXCLUDED.trace_id,
                    apex_trace = EXCLUDED.apex_trace,
                    updated_at = now()
                """,
                {
                    "sid": signal_id.strip()[:2000],
                    "eid": eid,
                    "tid": str(apex_trace.get("trace_id") or "") or None,
                    "apex": Json(_json_safe(apex_trace)),
                },
            )

    def _connect(self) -> Any:
        if self._pool is not None:
            return self._pool.connection()
        return cast(
            psycopg.Connection[Any],
            psycopg.connect(
                self._dsn,
                row_factory=cast(Any, dict_row),
                connect_timeout=5,
            ),
        )
