"""Prometheus-Gauges fuer Stream-Lag und Datenfrische (nur monitor-engine)."""

from __future__ import annotations

from prometheus_client import Gauge, Histogram

REDIS_STREAM_LAG = Gauge(
    "redis_stream_lag",
    "Schaetzwert Consumer-Lag (Redis lag oder Heuristik)",
    ["stream", "group"],
)

DATA_FRESHNESS_SECONDS = Gauge(
    "data_freshness_seconds",
    "Alter der letzten Daten in Sekunden",
    ["datapoint"],
)

# 0=ok, 1=warn, 2=shadow_only, 3=hard_block (shared_py.online_drift.action_rank)
ONLINE_DRIFT_ACTION_RANK = Gauge(
    "online_drift_action_rank",
    "Materialisierter Online-Drift (learn.online_drift_state), Rang der effektiven Aktion",
)

# Shadow-Live-Divergenz (live.execution_decisions, Prompt 28)
SHADOW_LIVE_GATE_BLOCKS_24H = Gauge(
    "shadow_live_gate_blocks_24h",
    "Entscheidungen mit decision_reason=shadow_live_divergence_gate (24h)",
)
SHADOW_LIVE_MATCH_FAILURES_24H = Gauge(
    "shadow_live_match_failures_24h",
    "Live-Pfad-Entscheidungen mit shadow_live_divergence.match_ok=false (24h)",
)

# Live-Broker / Reconcile (Monitor-Tick, aus Service-Checks + SQL)
LIVE_RECONCILE_AGE_MS = Gauge(
    "live_reconcile_age_ms",
    "Alter des letzten Reconcile-Snapshots in ms (-1 wenn unbekannt)",
)
LIVE_RECONCILE_DRIFT_TOTAL = Gauge(
    "live_reconcile_drift_total",
    "Drift total_count aus letztem Reconcile details_json.drift",
)
LIVE_KILL_SWITCH_ACTIVE_COUNT = Gauge(
    "live_kill_switch_active_count",
    "Aktive Kill-Switches (distinct scope/key)",
)
LIVE_SAFETY_LATCH_ACTIVE = Gauge(
    "live_safety_latch_active",
    "1 wenn Safety-Latch (Post-Reconcile-Fail) aktiv — Live-Fire blockiert",
)

# Trading / Pipeline (SQL-Aggregate, Monitor-Tick)
LIVE_ORDER_FAIL_RATE_1H = Gauge(
    "live_order_fail_rate_1h",
    "Anteil Orders mit Terminal-Fehlerstatus in der letzten Stunde (0..1)",
)
LIVE_FILL_SLIPPAGE_BPS_AVG_24H = Gauge(
    "live_fill_slippage_bps_avg_24h",
    "Mittlere abs. Slippage in bps (Limit-Orders mit Fill, 24h)",
)
LIVE_ORDER_ROUNDTRIP_P90_SECONDS = Gauge(
    "live_order_roundtrip_p90_seconds",
    "90. Perzentil Order-Lebensdauer filled (24h), Proxy fuer Latenz",
)
LEARN_DRIFT_EVENTS_24H = Gauge(
    "learn_drift_events_24h",
    "Anzahl learn.drift_events in 24h",
)
SIGNAL_PIPELINE_REJECTED_RATIO_24H = Gauge(
    "signal_pipeline_rejected_ratio_24h",
    "Anteil app.signals_v1 mit decision_state=rejected (24h)",
)
ALERT_OUTBOX_PENDING = Gauge(
    "alert_outbox_pending",
    "Ausstehende alert.alert_outbox Eintraege (state=pending)",
)
MONITOR_OPEN_ALERTS = Gauge(
    "monitor_open_alerts",
    "Offene ops.alerts (Monitor-Engine Upserts)",
)

# --- Prompt 32: zusaetzliche Betriebsmetriken (SQL-/Check-gestuetzt) ---

SIGNAL_PIPELINE_THROUGHPUT_1H = Gauge(
    "signal_pipeline_throughput_1h",
    "Anzahl app.signals_v1 Zeilen in der letzten Stunde (Feed-/Engine-Durchsatz)",
)

EXECUTION_DECISIONS_BLOCKED_24H = Gauge(
    "execution_decisions_blocked_24h",
    "live.execution_decisions mit decision_action=blocked in 24h (Risk-/Gate-Blocks)",
)

LIVE_ORDERS_OPEN = Gauge(
    "live_orders_open",
    "live.orders ohne Terminal-Status (offene/ausstehende Boersenorders)",
)

PAPER_POSITIONS_OPEN = Gauge(
    "paper_positions_open",
    "paper.positions mit state IN (open, partially_closed)",
)

LIVE_ORDER_EXIT_FAILURES_1H = Gauge(
    "live_order_exit_failures_1h",
    "live.orders mit status IN (flatten_failed, error) in der letzten Stunde",
)

SHADOW_LIVE_ASSESSMENT_MISMATCH_24H = Gauge(
    "shadow_live_assessment_mismatch_24h",
    "live.shadow_live_assessments mit match_ok=false in 24h (Replay/Shadow-Divergenz)",
)

LIVE_CRITICAL_AUDITS_24H = Gauge(
    "live_critical_audits_24h",
    "live.audit_trails severity=critical im Monitor-Lookback-Fenster",
)

SIGNAL_DO_NOT_TRADE_RATIO_1H = Gauge(
    "signal_do_not_trade_ratio_1h",
    "Anteil trade_action in (do_not_trade, abstain) in app.signals_v1 (1h)",
)
SIGNAL_STOP_FRAGILITY_P90_24H = Gauge(
    "signal_stop_fragility_p90_24h",
    "90. Perzentil stop_fragility_0_1 (24h, nur non-null)",
)
ALERT_OUTBOX_FAILED_24H = Gauge(
    "alert_outbox_failed_24h",
    "alert.alert_outbox state=failed in 24h",
)
SIGNAL_ROUTER_SWITCHES_24H = Gauge(
    "signal_router_switches_24h",
    "Anzahl Router-Wechsel zwischen aufeinanderfolgenden Signalen je Symbol/TF (24h, aggregiert)",
)
SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_24H = Gauge(
    "signal_specialist_disagreement_ratio_24h",
    "Anteil Signale mit adversary dissent / Router-Ueberstimmung / Ensemble-Schrumpfung (24h)",
)
TELEGRAM_OPERATOR_ERRORS_24H = Gauge(
    "telegram_operator_errors_24h",
    "alert.operator_action_audit mit executed_error/rejected_http_error/rejected_missing_upstream (24h)",
)
GATEWAY_AUTH_FAILURES_1H = Gauge(
    "gateway_auth_failures_1h",
    "Anzahl app.gateway_request_audit action LIKE auth_failure_* in der letzten Stunde",
)

# Monitor-Engine Tick (Scheduler) — Betriebs-SLI
MONITOR_ENGINE_TICK_DURATION_SECONDS = Histogram(
    "monitor_engine_tick_duration_seconds",
    "Dauer eines vollstaendigen Monitor-Ticks (Sekunden)",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# Signal-Pipeline: Feature computed_ts -> analysis_ts (P95, 1h)
SIGNAL_PIPELINE_LAG_P95_SECONDS_1H = Gauge(
    "signal_pipeline_lag_p95_seconds_1h",
    "P95 Latenz Sekunden: analysis_ts_ms minus feature_snapshot.primary_tf.computed_ts_ms (1h)",
)

# Manuelle Aktionen / Live-Broker-Mutationen: gezielte Auth-Fails
GATEWAY_MANUAL_ACTION_AUTH_FAILURES_1H = Gauge(
    "gateway_manual_action_auth_failures_1h",
    "auth_failure_manual_action_token + live_broker_mutation*_failures in 1h",
)

# Drift-/Shadow-bezogene Execution-Entscheidungen
EXECUTION_DRIFT_OR_SHADOW_DECISIONS_24H = Gauge(
    "execution_drift_or_shadow_decisions_24h",
    "execution_decisions mit decision_reason passend zu drift/online_drift/shadow_live (24h)",
)

# Commerce (optional — Tabellen leer wenn Modul aus)
COMMERCE_LEDGER_LINES_1H = Gauge(
    "commerce_ledger_lines_1h",
    "Anzahl app.usage_ledger Zeilen in der letzten Stunde",
)
COMMERCE_BILLING_AUTH_FAILURES_1H = Gauge(
    "commerce_billing_auth_failures_1h",
    "gateway_request_audit auth_failure_billing_read in 1h",
)

# Inference-Server (TimesFM gRPC) — Batch-Latenz (Push via /ops/inference-batch-metric)
TIMESFM_INFERENCE_BATCH_LATENCY_MS = Histogram(
    "timesfm_inference_batch_latency_ms",
    "Zeitreihen-Batch-Inferenz-Latenz in ms (inference-server -> monitor-engine)",
    ["model_id", "backend"],
    buckets=(0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 3000, 10000, 30000, 120000),
)
