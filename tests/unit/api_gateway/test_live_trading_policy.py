from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (REPO_ROOT, GATEWAY_SRC, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.auth import GatewayAuthContext
from api_gateway.deps import (
    LIVE_TRADING_NOT_ALLOWED_ERROR_CODE,
    verify_live_trading_capability,
)

from shared_py.product_policy import ExecutionPolicyViolationError


def _ctx(
    *,
    roles: set[str],
    method: str = "jwt",
    tenant_id: str | None = "t-tenant-1",
) -> GatewayAuthContext:
    return GatewayAuthContext(
        actor="u1",
        auth_method=method,
        roles=frozenset(roles),
        tenant_id=tenant_id,
    )


def _mock_settings(
    *,
    enforce: bool = True,
    ttl: int = 0,
) -> MagicMock:
    m = MagicMock()
    m.live_broker_gateway_live_policy_enforce = enforce
    m.commercial_default_tenant_id = "default"
    m.live_broker_gateway_live_policy_cache_ttl_sec = ttl
    return m


def test_verify_live_trading_bypasses_admin_write() -> None:
    with patch("api_gateway.deps.get_gateway_settings", return_value=_mock_settings()):
        verify_live_trading_capability(
            _ctx(roles={"admin:write", "operator:mutate"}),
        )


def test_verify_live_trading_bypasses_gateway_internal_key() -> None:
    with patch("api_gateway.deps.get_gateway_settings", return_value=_mock_settings()):
        verify_live_trading_capability(
            _ctx(roles={"operator:mutate"}, method="gateway_internal_key"),
        )


def test_verify_live_trading_403_when_db_denies() -> None:
    auth = _ctx(roles={"operator:mutate", "emergency:mutate"})
    with patch("api_gateway.deps.get_gateway_settings", return_value=_mock_settings(ttl=0)):
        with patch(
            "api_gateway.deps._read_live_ok_from_cache",
            return_value=None,
        ):
            with patch(
                "api_gateway.deps._live_policy_db_check",
                side_effect=ExecutionPolicyViolationError(
                    "nope",
                    reason="no_active_commercial_contract",
                ),
            ):
                with pytest.raises(HTTPException) as ei:
                    verify_live_trading_capability(auth)
    assert ei.value.status_code == 403
    assert ei.value.detail == {"error": LIVE_TRADING_NOT_ALLOWED_ERROR_CODE}


def test_verify_skipped_when_enforce_off() -> None:
    with patch("api_gateway.deps.get_gateway_settings", return_value=_mock_settings(enforce=False)):
        with patch("api_gateway.deps._live_policy_db_check") as m:
            verify_live_trading_capability(_ctx(roles={"operator:mutate"}))
    m.assert_not_called()
