from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from config.gateway_settings import GatewaySettings, get_gateway_settings
from config.internal_service_discovery import http_base_from_health_or_ready_url


def _clear() -> None:
    get_gateway_settings.cache_clear()


def test_gateway_rejects_loopback_health_urls_when_docker_dsn_enabled(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch.dict(
        os.environ,
        {
            "BITGET_USE_DOCKER_DATASTORE_DSN": "true",
            "DATABASE_URL": "postgresql://u:p@postgres:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "HEALTH_URL_MARKET_STREAM": "http://127.0.0.1:8010/ready",
            "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
        },
        clear=True,
    ):
        _clear()
        with pytest.raises(ValueError, match="HEALTH_URL_MARKET_STREAM"):
            GatewaySettings()
        _clear()


def test_gateway_rejects_loopback_llm_orch_base_when_docker_dsn_enabled(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch.dict(
        os.environ,
        {
            "BITGET_USE_DOCKER_DATASTORE_DSN": "true",
            "DATABASE_URL": "postgresql://u:p@postgres:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
            "HEALTH_URL_MARKET_STREAM": "http://market-stream:8010/ready",
            "HEALTH_URL_FEATURE_ENGINE": "http://feature-engine:8020/ready",
            "HEALTH_URL_STRUCTURE_ENGINE": "http://structure-engine:8030/ready",
            "HEALTH_URL_SIGNAL_ENGINE": "http://signal-engine:8050/ready",
            "HEALTH_URL_DRAWING_ENGINE": "http://drawing-engine:8040/ready",
            "HEALTH_URL_NEWS_ENGINE": "http://news-engine:8060/ready",
            "HEALTH_URL_LLM_ORCHESTRATOR": "http://llm-orchestrator:8070/ready",
            "LLM_ORCH_BASE_URL": "http://127.0.0.1:8070",
            "HEALTH_URL_PAPER_BROKER": "http://paper-broker:8085/ready",
            "HEALTH_URL_LEARNING_ENGINE": "http://learning-engine:8090/ready",
            "HEALTH_URL_ALERT_ENGINE": "http://alert-engine:8100/ready",
            "HEALTH_URL_MONITOR_ENGINE": "http://monitor-engine:8110/ready",
            "HEALTH_URL_LIVE_BROKER": "http://live-broker:8120/ready",
        },
        clear=True,
    ):
        _clear()
        with pytest.raises(ValueError, match="LLM_ORCH_BASE_URL"):
            GatewaySettings()
        _clear()


def test_gateway_rejects_loopback_live_broker_base_when_docker_dsn_enabled(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch.dict(
        os.environ,
        {
            "BITGET_USE_DOCKER_DATASTORE_DSN": "true",
            "DATABASE_URL": "postgresql://u:p@postgres:5432/db",
            "REDIS_URL": "redis://redis:6379/0",
            "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
            "HEALTH_URL_MARKET_STREAM": "http://market-stream:8010/ready",
            "HEALTH_URL_FEATURE_ENGINE": "http://feature-engine:8020/ready",
            "HEALTH_URL_STRUCTURE_ENGINE": "http://structure-engine:8030/ready",
            "HEALTH_URL_SIGNAL_ENGINE": "http://signal-engine:8050/ready",
            "HEALTH_URL_DRAWING_ENGINE": "http://drawing-engine:8040/ready",
            "HEALTH_URL_NEWS_ENGINE": "http://news-engine:8060/ready",
            "HEALTH_URL_LLM_ORCHESTRATOR": "http://llm-orchestrator:8070/ready",
            "LLM_ORCH_BASE_URL": "http://llm-orchestrator:8070",
            "HEALTH_URL_PAPER_BROKER": "http://paper-broker:8085/ready",
            "HEALTH_URL_LEARNING_ENGINE": "http://learning-engine:8090/ready",
            "HEALTH_URL_ALERT_ENGINE": "http://alert-engine:8100/ready",
            "HEALTH_URL_MONITOR_ENGINE": "http://monitor-engine:8110/ready",
            "HEALTH_URL_LIVE_BROKER": "http://live-broker:8120/ready",
            "LIVE_BROKER_BASE_URL": "http://localhost:8120",
        },
        clear=True,
    ):
        _clear()
        with pytest.raises(ValueError, match="LIVE_BROKER_BASE_URL"):
            GatewaySettings()
        _clear()


def test_live_broker_http_base_derives_from_health_when_base_url_empty(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    env = {
        "BITGET_USE_DOCKER_DATASTORE_DSN": "true",
        "DATABASE_URL": "postgresql://u:p@postgres:5432/db",
        "REDIS_URL": "redis://redis:6379/0",
        "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
        "HEALTH_URL_MARKET_STREAM": "http://market-stream:8010/ready",
        "HEALTH_URL_FEATURE_ENGINE": "http://feature-engine:8020/ready",
        "HEALTH_URL_STRUCTURE_ENGINE": "http://structure-engine:8030/ready",
        "HEALTH_URL_SIGNAL_ENGINE": "http://signal-engine:8050/ready",
        "HEALTH_URL_DRAWING_ENGINE": "http://drawing-engine:8040/ready",
        "HEALTH_URL_NEWS_ENGINE": "http://news-engine:8060/ready",
        "HEALTH_URL_LLM_ORCHESTRATOR": "http://llm-orchestrator:8070/ready",
        "LLM_ORCH_BASE_URL": "http://llm-orchestrator:8070",
        "HEALTH_URL_PAPER_BROKER": "http://paper-broker:8085/ready",
        "HEALTH_URL_LEARNING_ENGINE": "http://learning-engine:8090/ready",
        "HEALTH_URL_ALERT_ENGINE": "http://alert-engine:8100/ready",
        "HEALTH_URL_MONITOR_ENGINE": "http://monitor-engine:8110/ready",
        "HEALTH_URL_LIVE_BROKER": "http://live-broker:8120/ready",
        "LIVE_BROKER_BASE_URL": "",
    }
    with patch.dict(os.environ, env, clear=True):
        _clear()
        g = GatewaySettings()
        assert g.live_broker_http_base() == "http://live-broker:8120"
        assert g.live_broker_http_base() == http_base_from_health_or_ready_url(
            g.health_url_live_broker
        )
        _clear()


def test_gateway_accepts_service_name_health_when_docker_dsn_enabled(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alle HEALTH_URL_* mit Loopback-Defaults muessen auf Dienstnamen zeigen, sonst Fail-fast."""
    monkeypatch.chdir(tmp_path)
    env = {
        "BITGET_USE_DOCKER_DATASTORE_DSN": "true",
        "DATABASE_URL": "postgresql://u:p@postgres:5432/db",
        "REDIS_URL": "redis://redis:6379/0",
        "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
        "HEALTH_URL_MARKET_STREAM": "http://market-stream:8010/ready",
        "HEALTH_URL_FEATURE_ENGINE": "http://feature-engine:8020/ready",
        "HEALTH_URL_STRUCTURE_ENGINE": "http://structure-engine:8030/ready",
        "HEALTH_URL_SIGNAL_ENGINE": "http://signal-engine:8050/ready",
        "HEALTH_URL_DRAWING_ENGINE": "http://drawing-engine:8040/ready",
        "HEALTH_URL_NEWS_ENGINE": "http://news-engine:8060/ready",
        "HEALTH_URL_LLM_ORCHESTRATOR": "http://llm-orchestrator:8070/ready",
        "LLM_ORCH_BASE_URL": "http://llm-orchestrator:8070",
        "HEALTH_URL_PAPER_BROKER": "http://paper-broker:8085/ready",
        "HEALTH_URL_LEARNING_ENGINE": "http://learning-engine:8090/ready",
        "HEALTH_URL_ALERT_ENGINE": "http://alert-engine:8100/ready",
        "HEALTH_URL_MONITOR_ENGINE": "http://monitor-engine:8110/ready",
        "HEALTH_URL_LIVE_BROKER": "http://live-broker:8120/ready",
        # Explizit: sonst kann LIVE_BROKER_BASE_URL aus Host-.env.local (Loopback) die Docker-Validierung triggern.
        "LIVE_BROKER_BASE_URL": "http://live-broker:8120",
    }
    with patch.dict(os.environ, env, clear=True):
        _clear()
        g = GatewaySettings()
        assert "market-stream" in g.health_url_market_stream
        _clear()
