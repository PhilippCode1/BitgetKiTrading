from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from api_gateway.integrations_matrix import (
    build_integrations_matrix_payload,
    finalize_integrations_matrix_for_health,
    merge_persisted_integration_fields,
    roll_integration_connectivity_state,
)


def _g(**kwargs: object) -> SimpleNamespace:
    base = {
        "execution_mode": "paper",
        "live_broker_enabled": False,
        "live_trade_enable": False,
        "live_order_submission_enabled": False,
        "paper_path_active": True,
        "shadow_trade_enable": False,
        "telegram_dry_run": True,
        "telegram_bot_username": "",
        "commercial_telegram_required_for_console": False,
        "payment_checkout_enabled": False,
        "payment_stripe_enabled": False,
        "payment_mock_enabled": False,
        "payment_mode": "sandbox",
        "llm_use_fake_provider": False,
        "sensitive_auth_enforced": lambda: False,
        "gateway_auth_credentials_configured": lambda: True,
        "commercial_enabled": False,
        "bitget_demo_enabled": False,
        "vault_mode": "false",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_build_matrix_has_eight_integrations() -> None:
    services = [
        {"name": "market-stream", "status": "ok", "configured": True},
        {"name": "paper-broker", "status": "ok", "configured": True},
        {"name": "live-broker", "status": "not_configured", "configured": False},
        {"name": "feature-engine", "status": "ok", "configured": True},
        {"name": "structure-engine", "status": "ok", "configured": True},
        {"name": "signal-engine", "status": "ok", "configured": True},
        {"name": "drawing-engine", "status": "ok", "configured": True},
        {"name": "news-engine", "status": "ok", "configured": True},
        {"name": "learning-engine", "status": "ok", "configured": True},
        {"name": "alert-engine", "status": "ok", "configured": True},
        {"name": "llm-orchestrator", "status": "ok", "configured": True},
        {"name": "monitor-engine", "status": "ok", "configured": True},
    ]
    api, upsert = build_integrations_matrix_payload(
        _g(),
        services,
        database_status="ok",
        redis_status="ok",
        ops_summary={
            "monitor": {"open_alert_count": 0},
            "alert_engine": {"outbox_failed": 0},
        },
    )
    keys = {r["integration_key"] for r in api}
    assert keys == {
        "broker_exchange",
        "signal_pipeline",
        "learning_engine",
        "telegram",
        "payment_provider",
        "llm_ai",
        "monitoring",
        "dashboard_gateway",
    }
    assert len(upsert) == 8
    broker = next(x for x in api if x["integration_key"] == "broker_exchange")
    assert "BITGET_API_KEY" in broker["credential_refs"][0]
    assert broker["live_access"]["live_orders_explicitly_enabled"] is False
    assert broker["feature_flags"]["bitget_demo_enabled"] is False
    assert any("vault:bitget_api" in ref for ref in broker["credential_refs"])


def test_payment_misconfigured_stripe_live() -> None:
    def payment_environment() -> str:
        return "live"

    g = _g(
        payment_checkout_enabled=True,
        payment_stripe_enabled=True,
        payment_stripe_secret_key="",
        payment_stripe_webhook_secret="",
        payment_environment=payment_environment,
    )
    api, _ = build_integrations_matrix_payload(
        g,
        [],
        database_status="ok",
        redis_status="ok",
        ops_summary={},
    )
    pay = next(x for x in api if x["integration_key"] == "payment_provider")
    assert pay["health_status"] == "misconfigured"


def test_merge_persisted_adds_timestamps() -> None:
    api, _ = build_integrations_matrix_payload(
        _g(),
        [{"name": "paper-broker", "status": "ok", "configured": True}],
        database_status="ok",
        redis_status="ok",
        ops_summary={},
    )
    merged = merge_persisted_integration_fields(
        api,
        {
            "llm_ai": {
                "last_success_ts": "2026-01-01T00:00:00+00:00",
                "last_failure_ts": None,
                "last_error_public": None,
            }
        },
    )
    llm = next(x for x in merged if x["integration_key"] == "llm_ai")
    assert llm["last_success_ts"] == "2026-01-01T00:00:00+00:00"


def test_roll_integration_sets_success_timestamp() -> None:
    now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)
    r = roll_integration_connectivity_state(
        None,
        new_status="ok",
        new_error_public=None,
        server_now=now,
    )
    assert r["last_success_ts"] == now
    assert r["last_error_public"] is None


def test_finalize_wraps_matrix_with_policy() -> None:
    api, upsert = build_integrations_matrix_payload(
        _g(),
        [{"name": "paper-broker", "status": "ok", "configured": True}],
        database_status="ok",
        redis_status="ok",
        ops_summary={},
    )
    wrap, db_rows = finalize_integrations_matrix_for_health(
        api,
        upsert,
        {},
        g=_g(),
        server_now=datetime.now(UTC),
        server_ts_ms=1,
    )
    assert wrap["schema_version"] == "integrations-matrix-v1"
    assert wrap["credential_policy"]["reference_only"] is True
    assert len(wrap["integrations"]) == 8
    assert len(db_rows) == 8
