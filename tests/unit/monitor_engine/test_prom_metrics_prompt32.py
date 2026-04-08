"""Smoke: Prompt-32-Metriken sind im monitor-engine-Modul registrierbar."""

from __future__ import annotations

from monitor_engine.prom_metrics import (
    COMMERCE_BILLING_AUTH_FAILURES_1H,
    COMMERCE_LEDGER_LINES_1H,
    EXECUTION_DECISIONS_BLOCKED_24H,
    EXECUTION_DRIFT_OR_SHADOW_DECISIONS_24H,
    GATEWAY_AUTH_FAILURES_1H,
    GATEWAY_MANUAL_ACTION_AUTH_FAILURES_1H,
    LIVE_CRITICAL_AUDITS_24H,
    LIVE_ORDER_EXIT_FAILURES_1H,
    LIVE_ORDERS_OPEN,
    PAPER_POSITIONS_OPEN,
    SHADOW_LIVE_ASSESSMENT_MISMATCH_24H,
    MONITOR_ENGINE_TICK_DURATION_SECONDS,
    SIGNAL_DO_NOT_TRADE_RATIO_1H,
    SIGNAL_PIPELINE_LAG_P95_SECONDS_1H,
    SIGNAL_PIPELINE_THROUGHPUT_1H,
    SIGNAL_ROUTER_SWITCHES_24H,
    SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_24H,
    SIGNAL_STOP_FRAGILITY_P90_24H,
    TELEGRAM_OPERATOR_ERRORS_24H,
)


def test_prompt32_metric_names() -> None:
    assert SIGNAL_PIPELINE_THROUGHPUT_1H._name == "signal_pipeline_throughput_1h"
    assert EXECUTION_DECISIONS_BLOCKED_24H._name == "execution_decisions_blocked_24h"
    assert LIVE_ORDERS_OPEN._name == "live_orders_open"
    assert PAPER_POSITIONS_OPEN._name == "paper_positions_open"
    assert LIVE_ORDER_EXIT_FAILURES_1H._name == "live_order_exit_failures_1h"
    assert SHADOW_LIVE_ASSESSMENT_MISMATCH_24H._name == "shadow_live_assessment_mismatch_24h"
    assert LIVE_CRITICAL_AUDITS_24H._name == "live_critical_audits_24h"
    assert SIGNAL_DO_NOT_TRADE_RATIO_1H._name == "signal_do_not_trade_ratio_1h"
    assert SIGNAL_STOP_FRAGILITY_P90_24H._name == "signal_stop_fragility_p90_24h"
    assert SIGNAL_ROUTER_SWITCHES_24H._name == "signal_router_switches_24h"
    assert SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_24H._name == "signal_specialist_disagreement_ratio_24h"
    assert TELEGRAM_OPERATOR_ERRORS_24H._name == "telegram_operator_errors_24h"
    assert GATEWAY_AUTH_FAILURES_1H._name == "gateway_auth_failures_1h"
    assert MONITOR_ENGINE_TICK_DURATION_SECONDS._name == "monitor_engine_tick_duration_seconds"
    assert SIGNAL_PIPELINE_LAG_P95_SECONDS_1H._name == "signal_pipeline_lag_p95_seconds_1h"
    assert GATEWAY_MANUAL_ACTION_AUTH_FAILURES_1H._name == "gateway_manual_action_auth_failures_1h"
    assert EXECUTION_DRIFT_OR_SHADOW_DECISIONS_24H._name == "execution_drift_or_shadow_decisions_24h"
    assert COMMERCE_LEDGER_LINES_1H._name == "commerce_ledger_lines_1h"
    assert COMMERCE_BILLING_AUTH_FAILURES_1H._name == "commerce_billing_auth_failures_1h"
