from __future__ import annotations

from datetime import datetime, timedelta, timezone

from monitor_engine.checks.live_broker import build_live_broker_service_checks


def _status_map(snapshot: dict) -> dict[str, str]:
    now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    checks = build_live_broker_service_checks(
        snapshot,
        now_ms=int(now.timestamp() * 1000),
        reconcile_stale_ms=90_000,
        kill_switch_age_ms=300_000,
    )
    return {item.check_type: item.status for item in checks}


def test_live_broker_checks_flag_stale_reconcile() -> None:
    now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    statuses = _status_map(
        {
            "latest_reconcile": {
                "status": "ok",
                "created_ts": now - timedelta(minutes=3),
                "details_json": {"drift": {"total_count": 0}},
            },
            "active_kill_switches": [],
            "critical_audits": [],
            "last_fill_created_ts": None,
            "order_status_counts": {"submitted": 1},
            "shadow_live_stats": {"gate_blocks_24h": 0, "match_failures_24h": 0},
        }
    )
    assert statuses["reconcile"] == "fail"
    assert statuses["kill_switch"] == "ok"
    assert statuses["audit"] == "ok"
    assert statuses["shadow_live_divergence"] == "ok"


def test_live_broker_checks_flag_active_service_kill_switch() -> None:
    now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    statuses = _status_map(
        {
            "latest_reconcile": {
                "status": "ok",
                "created_ts": now,
                "details_json": {"drift": {"total_count": 0}},
            },
            "active_kill_switches": [
                {
                    "scope": "service",
                    "scope_key": "live-broker",
                    "reason": "ops_stop",
                    "source": "operator",
                    "created_ts": now - timedelta(seconds=30),
                }
            ],
            "critical_audits": [],
            "last_fill_created_ts": None,
            "order_status_counts": {},
            "shadow_live_stats": {"gate_blocks_24h": 0, "match_failures_24h": 0},
        }
    )
    assert statuses["kill_switch"] == "fail"
    assert statuses["shadow_live_divergence"] == "ok"


def test_live_broker_checks_flag_recent_critical_audit() -> None:
    now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    statuses = _status_map(
        {
            "latest_reconcile": {
                "status": "ok",
                "created_ts": now,
                "details_json": {"drift": {"total_count": 0}},
            },
            "active_kill_switches": [],
            "critical_audits": [
                {
                    "category": "emergency_flatten",
                    "action": "failed",
                    "scope": "account",
                    "scope_key": "USDT-FUTURES:USDT",
                    "symbol": "BTCUSDT",
                    "created_ts": now - timedelta(seconds=10),
                }
            ],
            "last_fill_created_ts": now - timedelta(seconds=5),
            "order_status_counts": {"timed_out": 1},
            "shadow_live_stats": {"gate_blocks_24h": 0, "match_failures_24h": 0},
        }
    )
    assert statuses["audit"] == "fail"


def test_shadow_live_check_degraded_when_gate_blocks_under_require_flag() -> None:
    now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    checks = build_live_broker_service_checks(
        {
            "latest_reconcile": {
                "status": "ok",
                "created_ts": now,
                "details_json": {
                    "drift": {"total_count": 0},
                    "execution_controls": {"require_shadow_match_before_live": True},
                },
            },
            "active_kill_switches": [],
            "critical_audits": [],
            "last_fill_created_ts": now,
            "order_status_counts": {},
            "shadow_live_stats": {"gate_blocks_24h": 2, "match_failures_24h": 0},
        },
        now_ms=int(now.timestamp() * 1000),
        reconcile_stale_ms=90_000,
        kill_switch_age_ms=300_000,
    )
    by_type = {c.check_type: c for c in checks}
    assert by_type["shadow_live_divergence"].status == "degraded"
    assert by_type["shadow_live_divergence"].details["gate_blocks_24h"] == 2
