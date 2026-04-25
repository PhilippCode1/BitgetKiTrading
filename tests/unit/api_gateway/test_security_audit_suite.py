"""
Security-Audit: negative Pfade (Auth, Header-Verwechslung, kein Leak fester Muster in 401-JSON).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def _env_local_stack(**overrides: str) -> dict[str, str]:
    from config.required_secrets import required_env_names_for_env_file_profile

    def _val(name: str) -> str:
        u = name.upper()
        if "DATABASE_URL" in u:
            return "postgresql://u:p@127.0.0.1:1/db"
        if "REDIS_URL" in u:
            return "redis://127.0.0.1:1/0"
        return "ci_repeatable_secret_min_32_chars_x"

    env = {k: _val(k) for k in required_env_names_for_env_file_profile(profile="local")}
    env.update(
        {
            "PRODUCTION": "false",
            "APP_ENV": "local",
            "COMMERCIAL_ENABLED": "true",
            "BITGET_DEMO_ENABLED": "false",
        }
    )
    env.update(overrides)
    return env


@pytest.fixture
def client_sensitive(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    e = _env_local_stack(
        GATEWAY_ENFORCE_SENSITIVE_AUTH="true",
        GATEWAY_JWT_SECRET="unit-test-gateway-jwt-secret-32b!",
    )
    for k, v in e.items():
        monkeypatch.setenv(k, v)
    _clear_gateway_settings_cache()
    from api_gateway.app import create_app

    return TestClient(create_app())


def _body_text(r) -> str:
    t = r.text or ""
    if "application/json" in (r.headers.get("content-type") or ""):
        try:
            return t + json.dumps(r.json(), default=str)
        except Exception:
            return t
    return t


def _jwt_token(
    *,
    secret: str,
    roles: list[str],
    role: str = "admin",
    portal_roles: list[str] | None = None,
    sub: str = "security-test",
) -> str:
    payload: dict[str, object] = {
        "sub": sub,
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
        "gateway_roles": roles,
        "role": role,
    }
    if portal_roles is not None:
        payload["portal_roles"] = portal_roles
    return jwt.encode(payload, secret, algorithm="HS256")


def test_bearer_garbage_not_jwt_401_and_no_config_leak(
    client_sensitive: TestClient,
) -> None:
    r = client_sensitive.get(
        "/v1/commerce/customer/me",
        headers={"Authorization": "Bearer not-a-jwt-just-ascii"},
    )
    assert r.status_code == 401, r.text
    t = _body_text(r)
    for bad in (
        "sk-proj",
        "ci_repeatable",
        "unit-test-gateway",
        "unit-test-gateway-jwt-secret-32b!",
    ):
        assert bad not in t


def test_service_internal_key_in_authorization_401(
    client_sensitive: TestClient,
) -> None:
    """Worker-Key-String in Authorization-Header: kein gueltiges HS256-JWT (401)."""
    r = client_sensitive.get(
        "/v1/commerce/customer/me",
        headers={"Authorization": "Bearer internal-service-key-12345"},
    )
    assert r.status_code == 401, r.text
    t = _body_text(r)
    assert "unit-test-gateway-jwt-secret-32b!" not in t


def test_unauthenticated_system_health_401_not_leak_secret(
    client_sensitive: TestClient,
) -> None:
    r = client_sensitive.get("/v1/system/health")
    assert r.status_code in (401, 403), r.text
    t = _body_text(r)
    assert "GATEWAY_JWT_SECRET" not in t
    assert "unit-test-gateway" not in t


def test_customer_portal_jwt_cannot_access_admin_route(client_sensitive: TestClient) -> None:
    secret = "unit-test-gateway-jwt-secret-32b!"
    token = _jwt_token(
        secret=secret,
        roles=["admin:read"],
        role="admin",
        portal_roles=["customer"],
    )
    r = client_sensitive.get(
        "/v1/admin/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "GATEWAY_FORBIDDEN_CUSTOMER_SESSION"


def test_wrong_scope_for_sensitive_mutation_is_403(client_sensitive: TestClient) -> None:
    secret = "unit-test-gateway-jwt-secret-32b!"
    token = _jwt_token(secret=secret, roles=["billing:read"], role="admin")
    r = client_sensitive.post(
        "/v1/live-broker/executions/00000000-0000-0000-0000-000000000001/operator-release",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "FORBIDDEN_MUTATION_ROLE"


def test_sensitive_mutation_requires_manual_action_token(
    client_sensitive: TestClient,
) -> None:
    secret = "unit-test-gateway-jwt-secret-32b!"
    token = _jwt_token(secret=secret, roles=["admin:write"], role="admin")
    r = client_sensitive.post(
        "/v1/live-broker/executions/00000000-0000-0000-0000-000000000001/operator-release",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "MANUAL_ACTION_TOKEN_REQUIRED"