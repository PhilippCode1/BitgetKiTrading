"""
Integration: gemeinsame Marker, optionale URLs und JWT fuer den API-Gateway-Stack.

Keine Produktions-Secrets: nur Umgebungsvariablen zur Laufzeit (lokal oder CI).
"""

from __future__ import annotations

import os

import jwt
import pytest

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore[assignment]

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_mock: Contract-Fixtures / Testdoubles ohne laufende Services",
    )
    config.addinivalue_line(
        "markers",
        "compose_smoke: optional; ruft scripts/integration_compose_smoke.sh auf",
    )
    config.addinivalue_line(
        "markers",
        "stack_recovery: DB/Redis-Recovery und Ops-Queries (Prompt 35)",
    )


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


@pytest.fixture(scope="session")
def integration_api_gateway_url() -> str:
    return _env("API_GATEWAY_URL")


@pytest.fixture(scope="session")
def integration_live_broker_url() -> str:
    return _env("INTEGRATION_LIVE_BROKER_URL") or _env("LIVE_BROKER_URL")


@pytest.fixture(scope="session")
def integration_gateway_jwt_secret() -> str:
    return _env("INTEGRATION_GATEWAY_JWT_SECRET")


def integration_bearer_token(*, secret: str, roles: list[str] | None = None) -> str:
    payload: dict = {
        "sub": "integration-test",
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
    }
    if roles is not None:
        payload["gateway_roles"] = roles
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="session")
def integration_auth_headers(integration_gateway_jwt_secret: str) -> dict[str, str]:
    if not integration_gateway_jwt_secret:
        return {}
    token = integration_bearer_token(
        secret=integration_gateway_jwt_secret,
        roles=["sensitive_read", "admin_read"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def integration_postgres_conn():
    """Echte Postgres-Verbindung; skip wenn TEST_DATABASE_URL fehlt oder Dienst down."""
    if psycopg is None:
        pytest.skip("psycopg nicht installiert")
    dsn = (os.getenv("TEST_DATABASE_URL") or "").strip()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL nicht gesetzt")
    try:
        conn = psycopg.connect(dsn, connect_timeout=5, autocommit=False)
    except Exception as exc:
        pytest.skip(f"Postgres nicht erreichbar: {exc}")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def integration_redis_client():
    """Redis-Client gegen TEST_REDIS_URL; skip wenn nicht erreichbar."""
    if redis is None:
        pytest.skip("redis-Paket nicht installiert")
    url = (os.getenv("TEST_REDIS_URL") or "").strip()
    if not url:
        pytest.skip("TEST_REDIS_URL nicht gesetzt")
    client = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
    try:
        client.ping()
    except Exception as exc:
        client.close()
        pytest.skip(f"Redis nicht erreichbar: {exc}")
    try:
        yield client
    finally:
        client.close()
