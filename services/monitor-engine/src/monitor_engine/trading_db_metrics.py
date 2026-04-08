"""SQL-Aggregate fuer Trading-/Pipeline-Prometheus-Metriken (Monitor-Tick)."""

from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("monitor_engine.trading_db_metrics")


def _one_float(conn: psycopg.Connection[Any], sql: str) -> float | None:
    row = conn.execute(sql).fetchone()
    if row is None:
        return None
    v = next(iter(row.values()))
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def refresh_trading_sql_metrics(dsn: str) -> None:
    """Setzt Prometheus-Gauges aus DB; einzelne Queries scheitern isoliert."""
    from monitor_engine.prom_metrics import (
        ALERT_OUTBOX_PENDING,
        COMMERCE_BILLING_AUTH_FAILURES_1H,
        COMMERCE_LEDGER_LINES_1H,
        EXECUTION_DECISIONS_BLOCKED_24H,
        EXECUTION_DRIFT_OR_SHADOW_DECISIONS_24H,
        GATEWAY_AUTH_FAILURES_1H,
        GATEWAY_MANUAL_ACTION_AUTH_FAILURES_1H,
        LEARN_DRIFT_EVENTS_24H,
        LIVE_FILL_SLIPPAGE_BPS_AVG_24H,
        LIVE_ORDER_EXIT_FAILURES_1H,
        LIVE_ORDER_FAIL_RATE_1H,
        LIVE_ORDER_ROUNDTRIP_P90_SECONDS,
        LIVE_ORDERS_OPEN,
        MONITOR_OPEN_ALERTS,
        PAPER_POSITIONS_OPEN,
        SHADOW_LIVE_ASSESSMENT_MISMATCH_24H,
        SIGNAL_PIPELINE_LAG_P95_SECONDS_1H,
        SIGNAL_PIPELINE_REJECTED_RATIO_24H,
        SIGNAL_PIPELINE_THROUGHPUT_1H,
        SIGNAL_DO_NOT_TRADE_RATIO_1H,
        SIGNAL_ROUTER_SWITCHES_24H,
        SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_24H,
        SIGNAL_STOP_FRAGILITY_P90_24H,
        ALERT_OUTBOX_FAILED_24H,
        TELEGRAM_OPERATOR_ERRORS_24H,
    )

    def _run(label: str, sql: str, gauge: Any, default: float = 0.0) -> None:
        try:
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
                v = _one_float(conn, sql)
            gauge.set(v if v is not None else default)
        except Exception as exc:
            logger.warning("trading_sql_metrics %s: %s", label, exc)

    _run(
        "order_fail_rate",
        """
        SELECT
          count(*) FILTER (
            WHERE lower(status) IN ('error', 'flatten_failed', 'timed_out')
          )::float / NULLIF(count(*), 0)
        FROM live.orders
        WHERE created_ts >= now() - interval '1 hour'
        """,
        LIVE_ORDER_FAIL_RATE_1H,
    )
    _run(
        "fill_slippage",
        """
        SELECT avg(
          abs((f.price::numeric - o.price::numeric) / NULLIF(o.price::numeric, 0)) * 10000
        )
        FROM live.fills f
        JOIN live.orders o ON o.internal_order_id = f.internal_order_id
        WHERE f.created_ts >= now() - interval '24 hours'
          AND o.price IS NOT NULL
          AND o.order_type = 'limit'
        """,
        LIVE_FILL_SLIPPAGE_BPS_AVG_24H,
    )
    _run(
        "order_roundtrip_p90",
        """
        SELECT percentile_cont(0.9) WITHIN GROUP (
          ORDER BY EXTRACT(EPOCH FROM (updated_ts - created_ts))
        )
        FROM live.orders
        WHERE created_ts >= now() - interval '24 hours'
          AND status = 'filled'
        """,
        LIVE_ORDER_ROUNDTRIP_P90_SECONDS,
    )
    _run(
        "drift_events",
        """
        SELECT count(*)::float
        FROM learn.drift_events
        WHERE detected_ts >= now() - interval '24 hours'
        """,
        LEARN_DRIFT_EVENTS_24H,
    )
    _run(
        "signal_rejected_ratio",
        """
        SELECT
          count(*) FILTER (WHERE decision_state = 'rejected')::float
          / NULLIF(count(*), 0)
        FROM app.signals_v1
        WHERE created_at >= now() - interval '24 hours'
        """,
        SIGNAL_PIPELINE_REJECTED_RATIO_24H,
    )
    _run(
        "alert_outbox_pending",
        """
        SELECT count(*)::float
        FROM alert.alert_outbox
        WHERE state = 'pending'
        """,
        ALERT_OUTBOX_PENDING,
    )
    _run(
        "ops_open_alerts",
        "SELECT count(*)::float FROM ops.alerts WHERE state = 'open'",
        MONITOR_OPEN_ALERTS,
    )
    _run(
        "signals_throughput_1h",
        """
        SELECT count(*)::float
        FROM app.signals_v1
        WHERE created_at >= now() - interval '1 hour'
        """,
        SIGNAL_PIPELINE_THROUGHPUT_1H,
    )
    _run(
        "execution_blocked_24h",
        """
        SELECT count(*)::float
        FROM live.execution_decisions
        WHERE decision_action = 'blocked'
          AND created_ts >= now() - interval '24 hours'
        """,
        EXECUTION_DECISIONS_BLOCKED_24H,
    )
    _run(
        "live_orders_open",
        """
        SELECT count(*)::float
        FROM live.orders
        WHERE status NOT IN (
          'canceled', 'filled', 'error', 'replaced', 'flattened', 'flatten_failed', 'timed_out'
        )
        """,
        LIVE_ORDERS_OPEN,
    )
    _run(
        "paper_positions_open",
        """
        SELECT count(*)::float
        FROM paper.positions
        WHERE state IN ('open', 'partially_closed')
        """,
        PAPER_POSITIONS_OPEN,
    )
    _run(
        "live_order_exit_failures_1h",
        """
        SELECT count(*)::float
        FROM live.orders
        WHERE status IN ('flatten_failed', 'error')
          AND updated_ts >= now() - interval '1 hour'
        """,
        LIVE_ORDER_EXIT_FAILURES_1H,
    )
    _run(
        "shadow_live_assessment_mismatch_24h",
        """
        SELECT count(*)::float
        FROM live.shadow_live_assessments
        WHERE match_ok = false
          AND created_ts >= now() - interval '24 hours'
        """,
        SHADOW_LIVE_ASSESSMENT_MISMATCH_24H,
    )
    _run(
        "signal_do_not_trade_ratio_1h",
        """
        SELECT
          count(*) FILTER (
            WHERE lower(coalesce(trade_action, '')) IN ('do_not_trade', 'abstain')
          )::float / NULLIF(count(*), 0)
        FROM app.signals_v1
        WHERE created_at >= now() - interval '1 hour'
        """,
        SIGNAL_DO_NOT_TRADE_RATIO_1H,
    )
    _run(
        "signal_stop_fragility_p90_24h",
        """
        SELECT percentile_cont(0.9) WITHIN GROUP (ORDER BY stop_fragility_0_1)
        FROM app.signals_v1
        WHERE created_at >= now() - interval '24 hours'
          AND stop_fragility_0_1 IS NOT NULL
        """,
        SIGNAL_STOP_FRAGILITY_P90_24H,
    )
    _run(
        "alert_outbox_failed_24h",
        """
        SELECT count(*)::float
        FROM alert.alert_outbox
        WHERE state = 'failed'
          AND created_ts >= now() - interval '24 hours'
        """,
        ALERT_OUTBOX_FAILED_24H,
    )
    _run(
        "signal_router_switches_24h",
        """
        WITH recent AS (
            SELECT symbol,
                   timeframe,
                   analysis_ts_ms,
                   COALESCE(
                       NULLIF(COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', ''),
                       NULLIF(COALESCE(source_snapshot_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', '')
                   ) AS router_id
            FROM app.signals_v1
            WHERE created_at >= now() - interval '24 hours'
        ),
        ordered AS (
            SELECT symbol,
                   timeframe,
                   analysis_ts_ms,
                   router_id,
                   lag(router_id) OVER (
                       PARTITION BY symbol, timeframe
                       ORDER BY analysis_ts_ms ASC
                   ) AS prev_router_id
            FROM recent
        )
        SELECT count(*)::float
        FROM ordered
        WHERE router_id IS NOT NULL
          AND prev_router_id IS NOT NULL
          AND router_id <> prev_router_id
        """,
        SIGNAL_ROUTER_SWITCHES_24H,
    )
    _run(
        "signal_specialist_disagreement_ratio_24h",
        """
        WITH recent AS (
            SELECT
                COALESCE(
                    NULLIF((COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'adversary_check'->>'dissent_score_0_1'), '')::numeric,
                    0
                ) AS dissent_score,
                COALESCE(
                    NULLIF((COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'ensemble_confidence_multiplier_0_1'), '')::numeric,
                    1
                ) AS ensemble_conf_mult,
                COALESCE(
                    COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'selected_trade_action',
                    ''
                ) AS selected_trade_action,
                COALESCE(
                    COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'pre_adversary_trade_action',
                    ''
                ) AS pre_adversary_trade_action,
                CASE
                    WHEN jsonb_typeof(COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'adversary_check'->'reasons') = 'array'
                    THEN jsonb_array_length(COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'adversary_check'->'reasons')
                    ELSE 0
                END AS adversary_reason_count
            FROM app.signals_v1
            WHERE created_at >= now() - interval '24 hours'
        )
        SELECT
            count(*) FILTER (
                WHERE dissent_score >= 0.35
                   OR adversary_reason_count > 0
                   OR ensemble_conf_mult < 0.95
                   OR (
                        selected_trade_action <> ''
                        AND pre_adversary_trade_action <> ''
                        AND selected_trade_action <> pre_adversary_trade_action
                   )
            )::float / NULLIF(count(*), 0)
        FROM recent
        """,
        SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_24H,
    )
    _run(
        "telegram_operator_errors_24h",
        """
        SELECT count(*)::float
        FROM alert.operator_action_audit
        WHERE outcome IN ('executed_error', 'rejected_http_error', 'rejected_missing_upstream')
          AND ts >= now() - interval '24 hours'
        """,
        TELEGRAM_OPERATOR_ERRORS_24H,
    )
    _run(
        "gateway_auth_failures_1h",
        """
        SELECT count(*)::float
        FROM app.gateway_request_audit
        WHERE action LIKE 'auth_failure_%'
          AND created_ts >= now() - interval '1 hour'
        """,
        GATEWAY_AUTH_FAILURES_1H,
    )
    _run(
        "signal_pipeline_lag_p95_1h",
        """
        WITH lags AS (
            SELECT
                (s.analysis_ts_ms - NULLIF(
                    (s.source_snapshot_json #>> '{feature_snapshot,primary_tf,computed_ts_ms}')::bigint,
                    0
                )) / 1000.0 AS lag_s
            FROM app.signals_v1 s
            WHERE s.created_at >= now() - interval '1 hour'
              AND s.source_snapshot_json #>> '{feature_snapshot,primary_tf,computed_ts_ms}' IS NOT NULL
        )
        SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY lag_s)
        FROM lags
        WHERE lag_s IS NOT NULL AND lag_s >= 0 AND lag_s < 7200
        """,
        SIGNAL_PIPELINE_LAG_P95_SECONDS_1H,
        default=-1.0,
    )
    _run(
        "gateway_manual_action_auth_failures_1h",
        """
        SELECT count(*)::float
        FROM app.gateway_request_audit
        WHERE created_ts >= now() - interval '1 hour'
          AND action IN (
              'auth_failure_manual_action_token',
              'auth_failure_live_broker_mutation',
              'auth_failure_live_broker_mutation_role'
          )
        """,
        GATEWAY_MANUAL_ACTION_AUTH_FAILURES_1H,
    )
    _run(
        "execution_drift_shadow_24h",
        """
        SELECT count(*)::float
        FROM live.execution_decisions
        WHERE created_ts >= now() - interval '24 hours'
          AND (
              lower(coalesce(decision_reason, '')) LIKE '%drift%'
              OR lower(coalesce(decision_reason, '')) LIKE '%online_drift%'
              OR lower(coalesce(decision_reason, '')) LIKE '%shadow_live%'
          )
        """,
        EXECUTION_DRIFT_OR_SHADOW_DECISIONS_24H,
    )
    _run(
        "commerce_ledger_lines_1h",
        """
        SELECT count(*)::float
        FROM app.usage_ledger
        WHERE created_ts >= now() - interval '1 hour'
        """,
        COMMERCE_LEDGER_LINES_1H,
    )
    _run(
        "commerce_billing_auth_failures_1h",
        """
        SELECT count(*)::float
        FROM app.gateway_request_audit
        WHERE action = 'auth_failure_billing_read'
          AND created_ts >= now() - interval '1 hour'
        """,
        COMMERCE_BILLING_AUTH_FAILURES_1H,
    )


def apply_live_broker_check_gauges(
    *,
    reconcile_details: dict[str, Any] | None,
    kill_switch_details: dict[str, Any] | None,
) -> None:
    from monitor_engine.prom_metrics import (
        LIVE_KILL_SWITCH_ACTIVE_COUNT,
        LIVE_RECONCILE_AGE_MS,
        LIVE_RECONCILE_DRIFT_TOTAL,
    )

    if reconcile_details:
        age = reconcile_details.get("latest_reconcile_age_ms")
        LIVE_RECONCILE_AGE_MS.set(float(age) if age is not None else -1.0)
        drift = reconcile_details.get("latest_reconcile_drift_total")
        LIVE_RECONCILE_DRIFT_TOTAL.set(float(drift) if drift is not None else 0.0)
    else:
        LIVE_RECONCILE_AGE_MS.set(-1.0)
        LIVE_RECONCILE_DRIFT_TOTAL.set(0.0)

    if kill_switch_details:
        c = kill_switch_details.get("active_kill_switch_count")
        LIVE_KILL_SWITCH_ACTIVE_COUNT.set(float(c) if c is not None else 0.0)
    else:
        LIVE_KILL_SWITCH_ACTIVE_COUNT.set(0.0)
