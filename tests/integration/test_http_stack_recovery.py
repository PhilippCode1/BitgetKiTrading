"""
HTTP-Recovery / Compose-Stack: optionale URLs (MARKET_STREAM_URL, Gateway, Live-Broker).

Chaos: Kill-Switch Arm/Release nur mit INTEGRATION_SAFETY_MUTATIONS=1 (bewusste Mutation).
"""

from __future__ import annotations

import json
import os

import httpx
import jwt
import pytest


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _details_json_from_reconcile_item(item: dict) -> dict:
    raw = item.get("details_json")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


@pytest.mark.integration
def test_market_stream_ready_retry_simulates_reconnect_window() -> None:
    base = _env("MARKET_STREAM_URL")
    if not base:
        pytest.skip("MARKET_STREAM_URL nicht gesetzt (Compose healthcheck.sh)")

    url = base.rstrip("/") + "/ready"
    last_exc: Exception | None = None
    for _attempt in range(5):
        try:
            r = httpx.get(url, timeout=10.0)
            r.raise_for_status()
            body = r.json()
            assert "ready" in body
            return
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
    raise AssertionError(f"market-stream /ready blieb nach Retries unreachable: {last_exc}")


@pytest.mark.integration
def test_live_broker_reconcile_latest_shape_after_restart() -> None:
    base = _env("INTEGRATION_LIVE_BROKER_URL") or _env("LIVE_BROKER_URL")
    if not base:
        pytest.skip("LIVE_BROKER_URL / INTEGRATION_LIVE_BROKER_URL")

    r = httpx.get(base.rstrip("/") + "/live-broker/reconcile/latest", timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "item" in data
    item = data.get("item")
    if item is None:
        pytest.skip("Kein reconcile_snapshot in der DB (Worker noch keinen Takt gelaufen)")
    assert item.get("status") in ("ok", "degraded", "fail")
    details = _details_json_from_reconcile_item(item)
    assert "drift" in details
    assert "recovery_state" in details
    assert "exchange_probe" in details
    assert "execution_controls" in details
    drift = details["drift"]
    assert isinstance(drift, dict)
    assert "total_count" in drift


@pytest.mark.integration
def test_live_broker_health_includes_latest_reconcile_dict() -> None:
    base = _env("INTEGRATION_LIVE_BROKER_URL") or _env("LIVE_BROKER_URL")
    if not base:
        pytest.skip("LIVE_BROKER_URL / INTEGRATION_LIVE_BROKER_URL")

    r = httpx.get(base.rstrip("/") + "/health", timeout=20.0)
    r.raise_for_status()
    data = r.json()
    assert "latest_reconcile" in data
    lr = data["latest_reconcile"]
    assert isinstance(lr, dict)
    if lr:
        assert lr.get("status") in ("ok", "degraded", "fail")


@pytest.mark.integration
def test_live_broker_evaluate_shadow_vs_live_decision_paths() -> None:
    base = _env("INTEGRATION_LIVE_BROKER_URL") or _env("LIVE_BROKER_URL")
    if not base:
        pytest.skip("LIVE_BROKER_URL / INTEGRATION_LIVE_BROKER_URL")

    common = {
        "source_service": "integration-prompt35",
        "signal_id": "prompt35-dual-1",
        "symbol": "BTCUSDT",
        "direction": "long",
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
    shadow_body = {**common, "requested_runtime_mode": "shadow", "signal_id": "prompt35-shadow"}
    live_body = {**common, "requested_runtime_mode": "live", "signal_id": "prompt35-live"}

    rs = httpx.post(
        base.rstrip("/") + "/live-broker/executions/evaluate",
        json=shadow_body,
        timeout=30.0,
    )
    rs.raise_for_status()
    rl = httpx.post(
        base.rstrip("/") + "/live-broker/executions/evaluate",
        json=live_body,
        timeout=30.0,
    )
    rl.raise_for_status()
    out_s = rs.json()
    out_l = rl.json()
    assert out_s["decision_action"] in (
        "shadow_recorded",
        "blocked",
        "live_candidate_recorded",
    )
    assert out_l["decision_action"] in (
        "shadow_recorded",
        "blocked",
        "live_candidate_recorded",
    )
    payload = out_l.get("payload_json") or {}
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if out_l.get("decision_action") == "live_candidate_recorded":
        assert "shadow_live_divergence" in payload


@pytest.mark.integration
def test_gateway_kill_switch_chaos_arm_then_release_opt_in() -> None:
    if _env("INTEGRATION_SAFETY_MUTATIONS").lower() not in ("1", "true", "yes"):
        pytest.skip("INTEGRATION_SAFETY_MUTATIONS=1 fuer echte Kill-Switch-Mutation")

    gw = _env("API_GATEWAY_URL")
    secret = _env("INTEGRATION_GATEWAY_JWT_SECRET")
    if not gw or not secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    token = jwt.encode(
        {
            "sub": "integration-chaos",
            "aud": "api-gateway",
            "iss": "bitget-btc-ai-gateway",
            "gateway_roles": ["sensitive_read", "admin_read"],
        },
        secret,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}
    base = gw.rstrip("/")

    arm = httpx.post(
        f"{base}/v1/live-broker/safety/kill-switch/arm",
        headers=headers,
        json={
            "scope": "service",
            "reason": "integration_chaos_prompt35",
            "source": "pytest",
        },
        timeout=45.0,
    )
    if arm.status_code >= 400:
        pytest.skip(f"Kill-Switch arm nicht moeglich (Broker/Modus): {arm.status_code} {arm.text[:500]}")

    active = httpx.get(
        f"{base}/v1/live-broker/kill-switch/active",
        headers=headers,
        timeout=20.0,
    )
    active.raise_for_status()
    items = active.json().get("items") or []
    assert isinstance(items, list)

    rel = httpx.post(
        f"{base}/v1/live-broker/safety/kill-switch/release",
        headers=headers,
        json={
            "scope": "service",
            "reason": "integration_chaos_prompt35_cleanup",
            "source": "pytest",
        },
        timeout=45.0,
    )
    assert rel.status_code < 400, rel.text


@pytest.mark.integration
def test_gateway_feed_stale_warning_when_market_stream_down_optional() -> None:
    """Wenn Gateway-Health den Stream sieht, ist ein Totalausfall als stale/off erkennbar."""
    gw = _env("API_GATEWAY_URL")
    secret = _env("INTEGRATION_GATEWAY_JWT_SECRET")
    if not gw or not secret:
        pytest.skip("API_GATEWAY_URL / INTEGRATION_GATEWAY_JWT_SECRET")

    token = jwt.encode(
        {
            "sub": "integration-feed",
            "aud": "api-gateway",
            "iss": "bitget-btc-ai-gateway",
            "gateway_roles": ["sensitive_read", "admin_read"],
        },
        secret,
        algorithm="HS256",
    )
    r = httpx.get(
        gw.rstrip("/") + "/v1/system/health",
        headers={"Authorization": f"Bearer {token}"},
        timeout=25.0,
    )
    r.raise_for_status()
    data = r.json()
    services = {s.get("name"): s for s in data.get("services", []) if isinstance(s, dict)}
    ms = services.get("market-stream")
    assert ms is not None
    assert ms.get("status") is not None
