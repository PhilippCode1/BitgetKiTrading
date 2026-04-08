from __future__ import annotations

from monitor_engine.alerts.rules import AlertSpec, alerts_from_service_checks
from monitor_engine.checks.services_http import ServiceCheckResult
from monitor_engine.trading_db_metrics import apply_live_broker_check_gauges


def test_kill_switch_alert_has_high_priority() -> None:
    specs = alerts_from_service_checks(
        [
            ServiceCheckResult(
                "live-broker",
                "kill_switch",
                "fail",
                None,
                {},
            ),
        ]
    )
    assert len(specs) == 1
    assert specs[0].priority == 5


def test_alert_specs_sort_safety_before_streams() -> None:
    stream = AlertSpec(
        alert_key="stream:x",
        severity="critical",
        title="s",
        message="m",
        details={},
        priority=40,
    )
    kill = AlertSpec(
        alert_key="svc:live-broker:kill_switch",
        severity="critical",
        title="k",
        message="m",
        details={},
        priority=5,
    )
    ordered = sorted(
        [stream, kill],
        key=lambda s: (s.priority, 0 if s.severity == "critical" else 1, s.alert_key),
    )
    assert ordered[0].alert_key.startswith("svc:live-broker:kill_switch")


def test_apply_live_broker_check_gauges_no_crash() -> None:
    apply_live_broker_check_gauges(
        reconcile_details={
            "latest_reconcile_age_ms": 1000,
            "latest_reconcile_drift_total": 3,
        },
        kill_switch_details={"active_kill_switch_count": 1},
    )
