"""SLO-/Schwellen-Alerts aus Trading-SQL (ergaenzt Service-/Freshness-Checks)."""

from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

from monitor_engine.alerts.rules import AlertSpec
from monitor_engine.config import MonitorEngineSettings

logger = logging.getLogger("monitor_engine.alerts.trading_sql")


def _one(conn: psycopg.Connection[Any], sql: str, params: tuple[Any, ...] | None = None) -> Any:
    row = conn.execute(sql, params or ()).fetchone()
    if row is None:
        return None
    return next(iter(dict(row).values()))


def collect_trading_sql_alerts(settings: MonitorEngineSettings) -> list[AlertSpec]:
    if not settings.monitor_trading_sql_alerts_enabled:
        return []
    out: list[AlertSpec] = []
    try:
        with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5) as conn:
            cnt = _one(
                conn,
                """
                SELECT count(*)::bigint AS c FROM app.signals_v1
                WHERE created_at >= now() - interval '1 hour'
                """,
            )
            cnt_i = int(cnt or 0)
            if cnt_i >= settings.monitor_min_signals_for_do_not_trade_ratio:
                ratio = _one(
                    conn,
                    """
                    SELECT
                      count(*) FILTER (
                        WHERE lower(coalesce(trade_action, '')) IN ('do_not_trade', 'abstain')
                      )::float / NULLIF(count(*), 0) AS r
                    FROM app.signals_v1
                    WHERE created_at >= now() - interval '1 hour'
                    """,
                )
                rf = float(ratio) if ratio is not None else 0.0
                if rf >= settings.thresh_signal_do_not_trade_ratio_warn:
                    out.append(
                        AlertSpec(
                            alert_key="trading:signal_do_not_trade_spike_1h",
                            severity="warn",
                            title="Signal-Pipeline: hoher No-Trade-Anteil (1h)",
                            message=f"Anteil do_not_trade/abstain={rf:.3f} bei n={cnt_i}",
                            details={"ratio_1h": rf, "count_1h": cnt_i},
                            priority=38,
                        )
                    )

            p90_frag = _one(
                conn,
                """
                SELECT percentile_cont(0.9) WITHIN GROUP (ORDER BY stop_fragility_0_1)
                FROM app.signals_v1
                WHERE created_at >= now() - interval '24 hours'
                  AND stop_fragility_0_1 IS NOT NULL
                """,
            )
            if p90_frag is not None:
                pf = float(p90_frag)
                if pf >= settings.thresh_stop_fragility_p90_warn:
                    out.append(
                        AlertSpec(
                            alert_key="trading:signal_stop_fragility_p90_elevated",
                            severity="warn",
                            title="Stop-Fragilitaet P90 (24h) erhoeht",
                            message=f"p90(stop_fragility_0_1)={pf:.4f}",
                            details={"p90_24h": pf},
                            priority=42,
                        )
                    )

            router_switches = _one(
                conn,
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
                SELECT count(*)::bigint
                FROM ordered
                WHERE router_id IS NOT NULL
                  AND prev_router_id IS NOT NULL
                  AND router_id <> prev_router_id
                """,
            )
            rs = int(router_switches or 0)
            if rs >= settings.thresh_signal_router_switches_24h_warn:
                out.append(
                    AlertSpec(
                        alert_key="trading:signal_router_instability_24h",
                        severity="warn",
                        title="Router-Instabilitaet im Spezialistenpfad (24h)",
                        message=f"Router-Wechsel ueber aufeinanderfolgende Signale={rs}",
                        details={"router_switches_24h": rs},
                        priority=41,
                    )
                )

            disagreement_ratio = _one(
                conn,
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
            )
            dr = float(disagreement_ratio) if disagreement_ratio is not None else 0.0
            if dr >= settings.thresh_signal_specialist_disagreement_ratio_warn:
                out.append(
                    AlertSpec(
                        alert_key="trading:specialist_disagreement_ratio_24h",
                        severity="warn",
                        title="Spezialisten-Disagreement erhoeht (24h)",
                        message=f"Anteil mit Dissent/Router-Ueberstimmung={dr:.3f}",
                        details={"disagreement_ratio_24h": dr},
                        priority=40,
                    )
                )

            failed_out = _one(
                conn,
                """
                SELECT count(*)::bigint AS c
                FROM alert.alert_outbox
                WHERE state = 'failed'
                  AND created_ts >= now() - interval '24 hours'
                """,
            )
            fi = int(failed_out or 0)
            if fi >= settings.thresh_alert_outbox_failed_warn:
                out.append(
                    AlertSpec(
                        alert_key="trading:telegram_outbox_failures_24h",
                        severity="warn",
                        title="Telegram/Alert-Outbox: Failed-Eintraege (24h)",
                        message=f"count(state=failed, 24h)={fi}",
                        details={"failed_count_24h": fi},
                        priority=30,
                    )
                )

            tg_errors = _one(
                conn,
                """
                SELECT count(*)::bigint AS c
                FROM alert.operator_action_audit
                WHERE outcome IN ('executed_error', 'rejected_http_error', 'rejected_missing_upstream')
                  AND ts >= now() - interval '24 hours'
                """,
            )
            tg_err_i = int(tg_errors or 0)
            if tg_err_i >= settings.thresh_telegram_operator_errors_24h_warn:
                out.append(
                    AlertSpec(
                        alert_key="trading:telegram_operator_errors_24h",
                        severity="warn",
                        title="Telegram-Operatorpfad mit Fehlern (24h)",
                        message=f"operator_action_audit Fehlercount={tg_err_i}",
                        details={"telegram_operator_errors_24h": tg_err_i},
                        priority=29,
                    )
                )

            auth_failures = _one(
                conn,
                """
                SELECT count(*)::bigint AS c
                FROM app.gateway_request_audit
                WHERE action LIKE 'auth_failure_%'
                  AND created_ts >= now() - interval '1 hour'
                """,
            )
            auth_i = int(auth_failures or 0)
            if auth_i >= settings.thresh_gateway_auth_failures_1h_warn:
                out.append(
                    AlertSpec(
                        alert_key="trading:gateway_auth_failures_1h",
                        severity="warn",
                        title="Gateway Auth-Anomalien (1h)",
                        message=f"auth_failure_* count={auth_i}",
                        details={"gateway_auth_failures_1h": auth_i},
                        priority=18,
                    )
                )

            drift = _one(
                conn,
                """
                SELECT COALESCE((details_json #>> '{drift,total_count}')::numeric, 0) AS d
                FROM live.reconcile_snapshots
                ORDER BY created_ts DESC
                LIMIT 1
                """,
            )
            if drift is not None:
                dv = float(drift)
                if dv >= float(settings.thresh_reconcile_drift_total_warn):
                    out.append(
                        AlertSpec(
                            alert_key="trading:live_reconcile_drift_elevated",
                            severity="warn",
                            title="Live-Reconcile: Drift total_count erhoeht",
                            message=f"latest drift.total_count={dv:.0f}",
                            details={"drift_total": dv},
                            priority=14,
                        )
                    )
    except Exception as exc:
        logger.warning("collect_trading_sql_alerts failed: %s", exc)
    return out
