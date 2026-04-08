from __future__ import annotations

from shared_py.health_warnings_display import (
    build_warnings_display,
    describe_health_warning,
)


def test_no_candles_timestamp_german_copy() -> None:
    d = describe_health_warning("no_candles_timestamp")
    assert d["code"] == "no_candles_timestamp"
    assert "Kerzen" in d["title"]
    assert "market-stream" in d["related_services"].lower() or "Market" in d["related_services"]
    assert d["machine"]["summary_en"]
    assert d["machine"]["problem_id"] == "health.no_candles_timestamp"


def test_build_warnings_display_order_preserved() -> None:
    codes = ["no_news_timestamp", "no_candles_timestamp"]
    rows = build_warnings_display(codes)
    assert [r["code"] for r in rows] == codes


def test_unknown_code_fallback_no_raw_as_title() -> None:
    d = describe_health_warning("totally_unknown_xyz")
    assert d["code"] == "totally_unknown_xyz"
    assert "totally_unknown_xyz" not in d["title"]
    assert d["title"]
    assert d["machine"]["schema_version"] == "health-warning-machine-v1"
    assert d["machine"]["problem_id"] == "health.unmapped.totally_unknown_xyz"


def test_dynamic_reconcile_message() -> None:
    d = describe_health_warning("live_broker_reconcile_stale")
    assert d["code"] == "live_broker_reconcile_stale"
    assert "stale" in d["message"].lower() or "Stale" in d["message"]


def test_monitor_open_count_enriches_message() -> None:
    ops = {"monitor": {"open_alert_count": 46}}
    d = describe_health_warning("monitor_alerts_open", ops_summary=ops)
    assert "46" in d["message"]
    assert "ops.alerts" in d["message"]
