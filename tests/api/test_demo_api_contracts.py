from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    cs = str(candidate)
    if cs not in sys.path:
        sys.path.insert(0, cs)

_MIN_ENV = {
    "PRODUCTION": "false",
    "APP_ENV": "local",
    "EXECUTION_MODE": "bitget_demo",
    "LIVE_TRADE_ENABLE": "false",
    "BITGET_DEMO_ENABLED": "true",
    "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
    "ADMIN_TOKEN": "unit_admin_token_for_tests_only________",
    "API_GATEWAY_URL": "http://127.0.0.1:8000",
    "DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/db",
    "DATABASE_URL_DOCKER": "postgresql://u:p@postgres:5432/db",
    "ENCRYPTION_KEY": "unit_encryption_key_32_chars_min______",
    "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
    "INTERNAL_API_KEY": "unit_internal_api_key_min_32_chars_x",
    "JWT_SECRET": "unit_jwt_secret_minimum_32_characters_",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "REDIS_URL_DOCKER": "redis://redis:6379/0",
    "SECRET_KEY": "unit_secret_key_minimum_32_characters",
    "BITGET_SKIP_MIGRATION_LATCH": "1",
}


@pytest.fixture
def client() -> TestClient:
    with (
        patch.dict(os.environ, _MIN_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        import api_gateway.app as app_module

        importlib.reload(app_module)
        with TestClient(app_module.create_app()) as tc:
            yield tc


def test_demo_readiness_contract(client: TestClient) -> None:
    r = client.get("/api/demo/readiness")
    assert r.status_code == 200
    body = r.json()
    assert "result" in body
    assert "demo_mode" in body


def test_demo_submit_blocked_contract(client: TestClient) -> None:
    r = client.post("/api/demo/order/submit")
    assert r.status_code == 200
    body = r.json()
    assert body.get("allowed") is False
    assert "blockgruende_de" in body
