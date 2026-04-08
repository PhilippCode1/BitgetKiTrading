from __future__ import annotations

from types import SimpleNamespace

from monitor_engine.alerts.trading_sql_alerts import collect_trading_sql_alerts


class _FakeCursor:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return {"value": self._value}


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=()):
        if "count(*)::bigint AS c FROM app.signals_v1" in sql:
            return _FakeCursor(20)
        if "do_not_trade" in sql and "interval '1 hour'" in sql:
            return _FakeCursor(0.91)
        if "percentile_cont(0.9) WITHIN GROUP (ORDER BY stop_fragility_0_1)" in sql:
            return _FakeCursor(0.88)
        if "router_id <> prev_router_id" in sql:
            return _FakeCursor(19)
        if "dissent_score" in sql and "ensemble_conf_mult" in sql:
            return _FakeCursor(0.44)
        if "FROM alert.alert_outbox" in sql and "state = 'failed'" in sql:
            return _FakeCursor(5)
        if "FROM alert.operator_action_audit" in sql:
            return _FakeCursor(4)
        if "FROM app.gateway_request_audit" in sql:
            return _FakeCursor(12)
        if "details_json #>> '{drift,total_count}'" in sql:
            return _FakeCursor(9)
        raise AssertionError(f"unerwartete SQL in Test: {sql[:160]}")


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        monitor_trading_sql_alerts_enabled=True,
        database_url="postgresql://test:test@localhost:5432/test",
        monitor_min_signals_for_do_not_trade_ratio=8,
        thresh_signal_do_not_trade_ratio_warn=0.82,
        thresh_stop_fragility_p90_warn=0.78,
        thresh_signal_router_switches_24h_warn=12,
        thresh_signal_specialist_disagreement_ratio_warn=0.35,
        thresh_alert_outbox_failed_warn=3,
        thresh_telegram_operator_errors_24h_warn=2,
        thresh_gateway_auth_failures_1h_warn=10,
        thresh_reconcile_drift_total_warn=5,
    )


def test_collect_trading_sql_alerts_includes_new_slos(monkeypatch) -> None:
    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: _FakeConn())
    specs = collect_trading_sql_alerts(_settings())
    keys = {spec.alert_key for spec in specs}
    assert "trading:signal_do_not_trade_spike_1h" in keys
    assert "trading:signal_stop_fragility_p90_elevated" in keys
    assert "trading:signal_router_instability_24h" in keys
    assert "trading:specialist_disagreement_ratio_24h" in keys
    assert "trading:telegram_outbox_failures_24h" in keys
    assert "trading:telegram_operator_errors_24h" in keys
    assert "trading:gateway_auth_failures_1h" in keys
    assert "trading:live_reconcile_drift_elevated" in keys


def test_collect_trading_sql_alerts_disabled_returns_empty() -> None:
    settings = _settings()
    settings.monitor_trading_sql_alerts_enabled = False
    assert collect_trading_sql_alerts(settings) == []
