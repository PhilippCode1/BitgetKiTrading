from __future__ import annotations

import asyncio
import importlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def _jwt(
    *,
    secret: str,
    roles: list[str] | None = None,
    sub: str = "tester",
    tenant_id: str | None = None,
    portal_roles: list[str] | None = None,
    platform_role: str | None = None,
) -> str:
    payload: dict = {
        "sub": sub,
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
    }
    if roles is not None:
        payload["gateway_roles"] = roles
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    if portal_roles is not None:
        payload["portal_roles"] = portal_roles
    if platform_role is not None:
        payload["platform_role"] = platform_role
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def _reset_rl_redis():
    import api_gateway.rate_limit as rl

    prev = rl._rl_redis
    rl._rl_redis = None
    yield
    rl._rl_redis = prev


def test_classify_path_live_and_admin() -> None:
    from api_gateway.rate_limit import _classify_path

    assert _classify_path("/v1/live/state") == "sensitive"
    assert _classify_path("/v1/admin/rules") == "admin"
    assert _classify_path("/v1/admin/llm-governance") == "admin"
    assert _classify_path("/v1/commerce/usage/summary") == "sensitive"


def test_is_safety_mutation_paths() -> None:
    from api_gateway.rate_limit import _is_safety_mutation

    assert _is_safety_mutation("/v1/live-broker/safety/orders/emergency-flatten", "POST")
    assert _is_safety_mutation(
        "/v1/live-broker/executions/00000000-0000-0000-0000-000000000001/operator-release",
        "POST",
    )
    assert not _is_safety_mutation("/v1/live-broker/safety/orders/emergency-flatten", "GET")
    assert not _is_safety_mutation("/v1/live-broker/runtime", "GET")


def test_super_admin_portal_stripped_when_subject_mismatch() -> None:
    from api_gateway.auth import resolve_gateway_auth

    secret = "unit-test-gateway-jwt-secret-32b!"
    tok = _jwt(
        secret=secret,
        roles=["billing:read"],
        sub="intruder",
        portal_roles=["super_admin"],
    )
    with patch.dict(
        os.environ,
        {
            "GATEWAY_JWT_SECRET": secret,
            "PRODUCTION": "false",
            "GATEWAY_SUPER_ADMIN_SUBJECT": "philipp-stable-sub",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        ctx = resolve_gateway_auth(
            request=MagicMock(),
            authorization=f"Bearer {tok}",
            x_gateway_internal_key=None,
            x_admin_token=None,
        )
    assert ctx is not None
    assert "super_admin" not in ctx.portal_roles
    assert ctx.access_matrix()["super_admin_portal"] is False


def test_super_admin_portal_kept_for_configured_subject() -> None:
    from api_gateway.auth import resolve_gateway_auth

    secret = "unit-test-gateway-jwt-secret-32b!"
    sub = "philipp-stable-sub"
    tok = _jwt(
        secret=secret,
        roles=["admin:write"],
        sub=sub,
        platform_role="super_admin",
    )
    with patch.dict(
        os.environ,
        {
            "GATEWAY_JWT_SECRET": secret,
            "PRODUCTION": "false",
            "GATEWAY_SUPER_ADMIN_SUBJECT": sub,
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        ctx = resolve_gateway_auth(
            request=MagicMock(),
            authorization=f"Bearer {tok}",
            x_gateway_internal_key=None,
            x_admin_token=None,
        )
    assert ctx is not None
    assert "super_admin" in ctx.portal_roles
    assert ctx.access_matrix()["super_admin_portal"] is True


def test_require_billing_read_rejects_pure_customer_without_tenant_when_commercial() -> None:
    from api_gateway.auth import require_billing_read

    async def _run() -> None:
        secret = "unit-test-gateway-jwt-secret-32b!"
        tok = _jwt(secret=secret, roles=["billing:read"], sub="cust-1")
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": secret,
                "PRODUCTION": "false",
                "COMMERCIAL_ENABLED": "true",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            req = MagicMock()
            with pytest.raises(HTTPException) as ei:
                await require_billing_read(
                    req,
                    authorization=f"Bearer {tok}",
                    x_gateway_internal_key=None,
                )
            assert ei.value.status_code == 403
            assert ei.value.detail["code"] == "TENANT_ID_REQUIRED"

    asyncio.run(_run())


def test_require_billing_read_accepts_pure_customer_with_tenant_when_commercial() -> None:
    from api_gateway.auth import require_billing_read

    async def _run() -> None:
        secret = "unit-test-gateway-jwt-secret-32b!"
        tok = _jwt(
            secret=secret,
            roles=["billing:read"],
            sub="cust-1",
            tenant_id="tenant-a",
        )
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": secret,
                "PRODUCTION": "false",
                "COMMERCIAL_ENABLED": "true",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            req = MagicMock()
            ctx = await require_billing_read(
                req,
                authorization=f"Bearer {tok}",
                x_gateway_internal_key=None,
            )
            assert ctx.tenant_id == "tenant-a"

    asyncio.run(_run())


def test_jwt_tenant_id_claim_parsed() -> None:
    import jwt as jwt_lib
    from api_gateway.auth import resolve_gateway_auth

    payload = {
        "sub": "t1",
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
        "gateway_roles": ["billing:read"],
        "tenant_id": " acme-corp ",
    }
    raw = jwt_lib.encode(
        payload, "unit-test-gateway-jwt-secret-32b!", algorithm="HS256"
    )
    with patch.dict(
        os.environ,
        {
            "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
            "PRODUCTION": "false",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        req = MagicMock()
        ctx = resolve_gateway_auth(
            request=req,
            authorization=f"Bearer {raw}",
            x_gateway_internal_key=None,
            x_admin_token=None,
        )
        assert ctx is not None
        assert ctx.tenant_id == "acme-corp"


def test_jwt_read_role_cannot_execute_emergency_route() -> None:
    from api_gateway.auth import GatewayAuthContext

    ctx = GatewayAuthContext(
        actor="u1",
        auth_method="jwt",
        roles=frozenset({"gateway:read"}),
    )
    from api_gateway.manual_action import ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN

    assert not ctx.can_execute_live_broker_route(ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN)


def test_jwt_emergency_role_can_execute() -> None:
    from api_gateway.auth import GatewayAuthContext
    from api_gateway.manual_action import ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN

    ctx = GatewayAuthContext(
        actor="u1",
        auth_method="jwt",
        roles=frozenset({"gateway:read", "emergency:mutate"}),
    )
    assert ctx.can_execute_live_broker_route(ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN)


def test_require_sensitive_auth_enforced_rejects_missing_credentials() -> None:
    from api_gateway.auth import require_sensitive_auth

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            req = MagicMock()
            with pytest.raises(HTTPException) as ei:
                await require_sensitive_auth(
                    req,
                    authorization=None,
                    x_gateway_internal_key=None,
                )
            assert ei.value.status_code == 401
            d = ei.value.detail
            assert isinstance(d, dict)
            assert d.get("code") == "GATEWAY_AUTH_MISSING"
            assert "INTERNAL_API_KEY" in str(d.get("hint", ""))

    asyncio.run(_run())


def test_require_sensitive_auth_accepts_jwt_with_read_role() -> None:
    from api_gateway.auth import require_sensitive_auth

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            tok = _jwt(secret="unit-test-gateway-jwt-secret-32b!", roles=["gateway:read"])
            req = MagicMock()
            ctx = await require_sensitive_auth(
                req,
                authorization=f"Bearer {tok}",
                x_gateway_internal_key=None,
            )
            assert ctx.can_sensitive_read()

    asyncio.run(_run())


def test_require_admin_write_forbids_customer_portal_jwt_even_with_write_role() -> None:
    """Kunden-Portal-Bearer darf Admin-APIs nicht nutzen, auch bei fehlgeleiteten admin:-Rollen."""
    from api_gateway.auth import require_admin_write

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            tok = _jwt(
                secret="unit-test-gateway-jwt-secret-32b!",
                roles=["admin:write"],
                portal_roles=["customer"],
            )
            req = MagicMock()
            with pytest.raises(HTTPException) as ei:
                await require_admin_write(
                    req,
                    authorization=f"Bearer {tok}",
                    x_gateway_internal_key=None,
                    x_admin_token=None,
                )
            assert ei.value.status_code == 403
            d = ei.value.detail
            assert isinstance(d, dict)
            assert d.get("code") == "GATEWAY_FORBIDDEN_CUSTOMER_SESSION"

    asyncio.run(_run())


def test_require_admin_read_allows_super_admin_portal_jwt() -> None:
    from api_gateway.auth import require_admin_read

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "GATEWAY_SUPER_ADMIN_SUBJECT": "tester",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            tok = _jwt(
                secret="unit-test-gateway-jwt-secret-32b!",
                roles=["admin:read"],
                platform_role="super_admin",
            )
            req = MagicMock()
            ctx = await require_admin_read(
                req,
                authorization=f"Bearer {tok}",
                x_gateway_internal_key=None,
                x_admin_token=None,
            )
            assert ctx.can_admin_read()

    asyncio.run(_run())


def test_require_admin_write_rejects_jwt_without_write() -> None:
    from api_gateway.auth import require_admin_write

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            tok = _jwt(secret="unit-test-gateway-jwt-secret-32b!", roles=["gateway:read"])
            req = MagicMock()
            with pytest.raises(HTTPException) as ei:
                await require_admin_write(
                    req,
                    authorization=f"Bearer {tok}",
                    x_gateway_internal_key=None,
                    x_admin_token=None,
                )
            assert ei.value.status_code == 401
            d = ei.value.detail
            assert isinstance(d, dict)
            assert d.get("code") == "GATEWAY_INSUFFICIENT_ROLES"
            assert d.get("required_capability") == "admin_write"

    asyncio.run(_run())


def test_resolve_gateway_auth_accepts_legacy_admin_token_when_enabled() -> None:
    from api_gateway.auth import resolve_gateway_auth

    with patch.dict(
        os.environ,
        {
            "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN": "true",
            "ADMIN_TOKEN": "legacy-admin-token",
            "PRODUCTION": "false",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        req = MagicMock()
        ctx = resolve_gateway_auth(
            request=req,
            authorization=None,
            x_gateway_internal_key=None,
            x_admin_token="legacy-admin-token",
        )
        assert ctx is not None
        assert ctx.auth_method == "legacy_admin_token"
        assert ctx.can_admin_write()


def test_require_live_stream_access_accepts_signed_sse_cookie() -> None:
    from api_gateway.auth import require_live_stream_access
    from api_gateway.config import get_gateway_settings
    from api_gateway.sse_ticket import build_sse_ticket, resolve_sse_signing_secret

    async def _run() -> None:
        with patch.dict(
            os.environ,
            {
                "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
                "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
                "PRODUCTION": "false",
            },
            clear=False,
        ):
            _clear_gateway_settings_cache()
            settings = get_gateway_settings()
            secret = resolve_sse_signing_secret(settings)
            assert secret is not None
            ticket = build_sse_ticket(secret=secret, sub="ops-user", ttl_sec=60)
            req = MagicMock()
            req.cookies = {settings.gateway_sse_cookie_name: ticket}
            ctx = await require_live_stream_access(
                req,
                authorization=None,
                x_gateway_internal_key=None,
            )
            assert ctx.auth_method == "sse_cookie"
            assert ctx.can_sensitive_read()

    asyncio.run(_run())


def test_resolve_gateway_auth_uses_gateway_internal_key_method() -> None:
    from api_gateway.auth import resolve_gateway_auth

    gk = "gateway-internal-key-32-chars-min!___"
    with patch.dict(
        os.environ,
        {
            "GATEWAY_INTERNAL_API_KEY": gk,
            "PRODUCTION": "false",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        ctx = resolve_gateway_auth(
            request=MagicMock(),
            authorization=None,
            x_gateway_internal_key=gk,
            x_admin_token=None,
        )
    assert ctx is not None
    assert ctx.auth_method == "gateway_internal_key"
    assert ctx.can_admin_write()


def test_gateway_internal_key_mismatch_returns_diagnostic() -> None:
    from api_gateway.auth import resolve_gateway_auth_with_diagnostic

    with patch.dict(
        os.environ,
        {
            "GATEWAY_INTERNAL_API_KEY": "expected-gateway-internal-32chars__",
            "PRODUCTION": "false",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        ctx, diag = resolve_gateway_auth_with_diagnostic(
            request=MagicMock(),
            authorization=None,
            x_gateway_internal_key="wrong-gateway-internal-key-32c_",
            x_admin_token=None,
        )
    assert ctx is None
    assert diag is not None
    assert diag["code"] == "GATEWAY_INTERNAL_KEY_MISMATCH"


def test_expired_jwt_returns_diagnostic() -> None:
    from api_gateway.auth import resolve_gateway_auth_with_diagnostic

    secret = "unit-test-gateway-jwt-secret-32b!"
    payload = {
        "sub": "u1",
        "aud": "api-gateway",
        "iss": "bitget-btc-ai-gateway",
        "gateway_roles": ["gateway:read"],
        "exp": int(time.time()) - 120,
    }
    tok = jwt.encode(payload, secret, algorithm="HS256")
    with patch.dict(
        os.environ,
        {
            "GATEWAY_JWT_SECRET": secret,
            "PRODUCTION": "false",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        ctx, diag = resolve_gateway_auth_with_diagnostic(
            request=MagicMock(),
            authorization=f"Bearer {tok}",
            x_gateway_internal_key=None,
            x_admin_token=None,
        )
    assert ctx is None
    assert diag is not None
    assert diag["code"] == "GATEWAY_JWT_EXPIRED"


def test_rate_limit_returns_429_when_count_exceeds_limit() -> None:
    """Öffentlicher Pfad, künstlich hoher Zähler -> 429 (PRODUCTION=false, Redis gemockt)."""

    class _HighIncr:
        def incr(self, _key: str) -> int:
            return 9999

        def expire(self, *_a, **_k) -> None:
            return None

    import api_gateway.rate_limit as rl

    rl._rl_redis = _HighIncr()
    with (
        patch.dict(os.environ, {"PRODUCTION": "false"}, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_k: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        client = TestClient(app_module.create_app())
        # /health ist vom Rate-Limit ausgenommen; oeffentlicher Pfad mit Limit
        r = client.get("/")
        assert r.status_code == 429
    _clear_gateway_settings_cache()
