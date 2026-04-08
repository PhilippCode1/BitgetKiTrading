from __future__ import annotations

from monitor_engine.alerts.operator_context import merge_operator_guidance


def test_merge_operator_guidance_freshness_has_correlation() -> None:
    d = merge_operator_guidance(
        alert_key="freshness:signals",
        base_details={"age_ms": 999000, "last_ts_ms": 1},
        severity="critical",
        title="Datenfrische signals",
        observed_at_ms=1710000000000,
    )
    assert d["operator_context_version"] == 1
    assert d["correlation"]["alert_family"] == "data_freshness"
    assert d["correlation"]["observed_at_ms"] == 1710000000000
    assert "signal-engine" in d["operator_affected_services"]
    assert d["age_ms"] == 999000


def test_merge_operator_guidance_stream_group() -> None:
    d = merge_operator_guidance(
        alert_key="stream:events:signals:group:signal-engine-cg",
        base_details={"pending_count": 3, "lag": 100},
        severity="warn",
        title="Redis Stream belastet",
        observed_at_ms=0,
    )
    assert d["correlation"]["alert_family"] == "redis_stream"
    assert len(d["operator_first_steps_de"]) >= 2


def test_merge_operator_guidance_svc_live_kill_switch() -> None:
    d = merge_operator_guidance(
        alert_key="svc:live-broker:kill_switch",
        base_details={"http_status": 200},
        severity="critical",
        title="x",
        observed_at_ms=1,
    )
    assert "runtime" in " ".join(d["operator_first_steps_de"]).lower()
