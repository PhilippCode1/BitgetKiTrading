"""Stale-Daten, Stream-Lag und Service-Degradation → AlertSpecs (Chaos-/Druck-Evidenz, rein unit)."""

from __future__ import annotations

import pytest

from monitor_engine.alerts.rules import (
    AlertSpec,
    alert_stream_stalled,
    alerts_from_freshness,
    alerts_from_service_checks,
    alerts_from_stream_checks,
)
from monitor_engine.checks.data_freshness import FreshnessRow
from monitor_engine.checks.redis_streams import StreamGroupCheckResult
from monitor_engine.checks.services_http import ServiceCheckResult


@pytest.mark.chaos
def test_freshness_critical_emits_high_priority_alert() -> None:
    rows = [
        FreshnessRow(
            datapoint="candles:BTCUSDT:1m",
            last_ts_ms=1,
            age_ms=900_000,
            status="critical",
            details={"source": "db"},
        )
    ]
    alerts = alerts_from_freshness(rows)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.alert_key == "freshness:candles:BTCUSDT:1m"
    assert a.severity == "critical"
    assert a.priority == 25
    assert a.details["age_ms"] == 900_000


@pytest.mark.chaos
def test_stream_lag_degraded_warn_priority() -> None:
    results = [
        StreamGroupCheckResult(
            stream="events:signal",
            group_name="gw",
            pending_count=200,
            lag=50,
            last_generated_id="1-0",
            last_delivered_id="0-0",
            status="degraded",
            details={"note": "pressure"},
        )
    ]
    alerts = alerts_from_stream_checks(results)
    assert len(alerts) == 1
    assert alerts[0].severity == "warn"
    assert "pending=200" in alerts[0].message


@pytest.mark.chaos
def test_live_broker_reconcile_degraded_maps_priority() -> None:
    checks = [
        ServiceCheckResult(
            service_name="live-broker",
            check_type="reconcile",
            status="degraded",
            latency_ms=8000,
            details={"lag_orders": 3},
        )
    ]
    alerts = alerts_from_service_checks(checks)
    assert len(alerts) == 1
    assert alerts[0].alert_key == "svc:live-broker:reconcile"
    assert alerts[0].priority == 12


@pytest.mark.chaos
def test_alert_stream_stalled_none_when_not_critical() -> None:
    assert alert_stream_stalled("x", candle_stale_critical=False) is None


@pytest.mark.chaos
def test_alert_stream_stalled_critical_shape() -> None:
    a = alert_stream_stalled("events:candles", candle_stale_critical=True)
    assert isinstance(a, AlertSpec)
    assert a.severity == "critical"
    assert a.priority == 15
