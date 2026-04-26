"""
HTTP-Integration: Gateway, Live-Broker, Paper, Learning, Monitor.

Ohne URL: pytest.skip (Standard-CI bleibt gruen).
"""

from __future__ import annotations

import os

import httpx
import jwt
import pytest


@pytest.mark.integration
def test_api_gateway_system_health_aggregate(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url:
        pytest.skip("API_GATEWAY_URL nicht gesetzt")
    if not integration_gateway_jwt_secret:
        pytest.skip("INTEGRATION_GATEWAY_JWT_SECRET fehlt (wie Gateway-JWT im Stack)")

    url = integration_api_gateway_url.rstrip("/") + "/v1/system/health"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert data.get("database") == "ok"
    assert data.get("redis") == "ok"
    services = {
        s.get("name"): s for s in data.get("services", []) if isinstance(s, dict)
    }
    for name in (
        "signal-engine",
        "paper-broker",
        "learning-engine",
        "live-broker",
        "monitor-engine",
    ):
        assert name in services, f"service {name} fehlt"
        assert str(services[name].get("status", "")).lower() == "ok"
    ops = data.get("ops")
    assert isinstance(ops, dict)
    lb = ops.get("live_broker")
    assert isinstance(lb, dict)
    assert "active_kill_switch_count" in lb
    assert "latest_reconcile_status" in lb
    assert "latest_reconcile_age_ms" in lb


@pytest.mark.integration
def test_gateway_paper_metrics_summary_dashboard_shape(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    url = integration_api_gateway_url.rstrip("/") + "/v1/paper/metrics/summary"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "equity_curve" in data


@pytest.mark.integration
def test_gateway_learning_registry_v2_shape(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    url = integration_api_gateway_url.rstrip("/") + "/v1/learning/models/registry-v2"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_gateway_strategy_registry_list_contract(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    base = integration_api_gateway_url.rstrip("/")
    r = httpx.get(
        f"{base}/v1/registry/strategies", headers=integration_auth_headers, timeout=20.0
    )
    r.raise_for_status()
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "signal_path_playbooks" in data
    assert isinstance(data["signal_path_playbooks"], list)
    if data["items"]:
        row0 = data["items"][0]
        assert "strategy_id" in row0
        assert "name" in row0
        assert "status" in row0
        assert "signal_path_signal_count" in row0


@pytest.mark.integration
def test_gateway_strategy_registry_detail_contract(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    base = integration_api_gateway_url.rstrip("/")
    r0 = httpx.get(
        f"{base}/v1/registry/strategies", headers=integration_auth_headers, timeout=20.0
    )
    r0.raise_for_status()
    items = r0.json().get("items") or []
    if not items:
        pytest.skip("Keine Strategie in learn.strategies fuer Detail-Test")

    sid = items[0]["strategy_id"]
    r1 = httpx.get(
        f"{base}/v1/registry/strategies/{sid}",
        headers=integration_auth_headers,
        timeout=20.0,
    )
    r1.raise_for_status()
    detail = r1.json()
    assert detail.get("strategy_id") == sid
    assert "lifecycle_status" in detail
    assert "performance_rolling" in detail
    assert "signal_path" in detail
    sp = detail.get("signal_path") or {}
    assert sp.get("registry_key") == detail.get("name")
    assert sp.get("signals_list_query_param") == "signal_registry_key"


@pytest.mark.integration
def test_gateway_monitor_alerts_open_shape(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    url = integration_api_gateway_url.rstrip("/") + "/v1/monitor/alerts/open"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_gateway_live_broker_kill_switch_active_shape(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    base_gw = integration_api_gateway_url.rstrip("/")
    url = f"{base_gw}/v1/live-broker/kill-switch/active"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_gateway_live_broker_runtime_operator_live_submission_shape(
    integration_api_gateway_url: str,
    integration_gateway_jwt_secret: str,
    integration_auth_headers: dict[str, str],
) -> None:
    if not integration_api_gateway_url or not integration_gateway_jwt_secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    base_gw = integration_api_gateway_url.rstrip("/")
    url = f"{base_gw}/v1/live-broker/runtime"
    r = httpx.get(url, headers=integration_auth_headers, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    item = data.get("item")
    if item is not None:
        ols = item.get("operator_live_submission")
        assert isinstance(ols, dict)
        assert ols.get("lane")
        assert "reasons_de" in ols
        assert "safety_kill_switch_count" in ols


@pytest.mark.integration
def test_live_broker_ready_and_execution_evaluate_shadow_path(
    integration_live_broker_url: str,
) -> None:
    base = integration_live_broker_url
    if not base:
        pytest.skip("INTEGRATION_LIVE_BROKER_URL oder LIVE_BROKER_URL nicht gesetzt")

    r0 = httpx.get(base.rstrip("/") + "/ready", timeout=20.0)
    r0.raise_for_status()
    ready = r0.json()
    assert ready.get("ready") is True
    checks = ready.get("checks") or {}
    assert isinstance(checks, dict)
    assert checks.get("execution_mode") in ("paper", "shadow", "live")

    body = {
        "source_service": "signal-engine",
        "signal_id": "integration-shadow-gate-1",
        "symbol": "BTCUSDT",
        "direction": "long",
        "requested_runtime_mode": "shadow",
        "leverage": 12,
        "approved_7x": False,
        "qty_base": "0.001",
        "entry_price": "50000",
        "stop_loss": "49000",
        "take_profit": "52000",
        "payload": {
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    }
    r1 = httpx.post(
        base.rstrip("/") + "/live-broker/executions/evaluate",
        json=body,
        timeout=30.0,
    )
    r1.raise_for_status()
    out = r1.json()
    assert "decision_action" in out
    assert "decision_reason" in out
    assert out["decision_action"] in (
        "shadow_recorded",
        "blocked",
        "live_candidate_recorded",
    )


@pytest.mark.integration
def test_gateway_sensitive_rejects_without_auth_when_enforced() -> None:
    if os.getenv("INTEGRATION_TEST_SENSITIVE_AUTH", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("INTEGRATION_TEST_SENSITIVE_AUTH=1 und Gateway-Enforce aktiv")

    base = (os.getenv("API_GATEWAY_URL") or "").strip()
    secret = (os.getenv("INTEGRATION_GATEWAY_JWT_SECRET") or "").strip()
    if not base or not secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    url = base.rstrip("/") + "/v1/paper/positions/open"
    r = httpx.get(url, timeout=15.0)
    assert r.status_code in (401, 403)


@pytest.mark.integration
def test_gateway_rate_limit_eventually_429_or_still_200() -> None:
    if os.getenv("INTEGRATION_TEST_RATE_LIMIT", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("INTEGRATION_TEST_RATE_LIMIT=1 optional (Redis-RL aktiv)")

    base = (os.getenv("API_GATEWAY_URL") or "").strip()
    secret = (os.getenv("INTEGRATION_GATEWAY_JWT_SECRET") or "").strip()
    if not base or not secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    payload = {
        "sub": "integration-rl",
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
        "gateway_roles": ["sensitive_read"],
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    url = base.rstrip("/") + "/v1/monitor/alerts/open"
    codes: list[int] = []
    with httpx.Client(headers=headers, timeout=15.0) as client:
        for _ in range(25):
            resp = client.get(url)
            codes.append(resp.status_code)
            if resp.status_code == 429:
                break
    assert 200 in codes or 429 in codes
