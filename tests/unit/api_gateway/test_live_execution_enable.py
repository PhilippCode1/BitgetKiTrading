from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (REPO_ROOT, GATEWAY_SRC, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.auth import GatewayAuthContext
from api_gateway.routes_commerce_customer import customer_live_execution_enable


def _ctx(
    *,
    roles: set[str],
    method: str = "jwt",
    tenant_id: str | None = "t-tenant-1",
) -> GatewayAuthContext:
    ctx = GatewayAuthContext(
        actor="u1",
        auth_method=method,
        roles=frozenset(roles),
        tenant_id=tenant_id,
    )
    # Mock `is_customer_portal_jwt` to return True for customer
    object.__setattr__(ctx, "portal_roles", frozenset({"customer"}))
    return ctx


@pytest.fixture
def mock_request() -> MagicMock:
    req = MagicMock(spec=Request)
    req.url.path = "/v1/commerce/customer/live-execution/enable"
    return req


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
def test_live_execution_enable_demo_mode_blocked(
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = True
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)
    
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "DEMO_MODE_ACTIVE"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
def test_live_execution_enable_missing_api_keys(
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    # Keys are incomplete
    mock_flags.return_value = (False, ["bitget_live_credentials_incomplete"])

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)
    
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "MISSING_API_KEYS"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
def test_live_execution_enable_invalid_api_keys(
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    mock_flags.return_value = (True, [])
    # Verification fails (e.g. key-ping returns 401 or invalid signature)
    mock_verify.return_value = False

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)
    
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "INVALID_API_KEYS"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.tenant_has_active_live_commercial_contract")
@patch("api_gateway.routes_commerce_customer.fetch_prepaid_balance_list_usd")
@patch("api_gateway.routes_commerce_customer.fetch_tenant_modul_mate_gates")
@patch("api_gateway.routes_commerce_customer.record_gateway_audit_line")
def test_live_execution_enable_contract_not_signed(
    mock_audit: MagicMock,
    mock_fetch_gates: MagicMock,
    mock_prepaid: MagicMock,
    mock_has_contract: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    mock_flags.return_value = (True, [])
    mock_verify.return_value = True

    # mock contract is missing
    mock_has_contract.return_value = False

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    # Mock the database connection block
    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)
    
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "CONTRACT_NOT_SIGNED"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.tenant_has_active_live_commercial_contract")
@patch("api_gateway.routes_commerce_customer.fetch_prepaid_balance_list_usd")
@patch("api_gateway.routes_commerce_customer.fetch_tenant_modul_mate_gates")
@patch("api_gateway.routes_commerce_customer.record_gateway_audit_line")
def test_live_execution_enable_insufficient_balance(
    mock_audit: MagicMock,
    mock_fetch_gates: MagicMock,
    mock_prepaid: MagicMock,
    mock_has_contract: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.billing_min_balance_new_trade_usd = "50"
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    mock_flags.return_value = (True, [])
    mock_verify.return_value = True
    mock_has_contract.return_value = True
    
    # Gates mock
    gates = MagicMock()
    gates.account_suspended = False
    gates.account_paused = False
    mock_fetch_gates.return_value = gates

    # Balance is below limit (e.g. 10.0 USD)
    mock_prepaid.return_value = Decimal("10.00")

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)
    
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "INSUFFICIENT_BALANCE"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.tenant_has_active_live_commercial_contract")
@patch("api_gateway.routes_commerce_customer.fetch_prepaid_balance_list_usd")
@patch("api_gateway.routes_commerce_customer.fetch_tenant_modul_mate_gates")
@patch("api_gateway.routes_commerce_customer.record_gateway_audit_line")
def test_live_execution_enable_success(
    mock_audit: MagicMock,
    mock_fetch_gates: MagicMock,
    mock_prepaid: MagicMock,
    mock_has_contract: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.billing_min_balance_new_trade_usd = "50"
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    mock_flags.return_value = (True, [])
    mock_verify.return_value = True
    mock_has_contract.return_value = True
    
    # Gates mock
    gates = MagicMock()
    gates.account_suspended = False
    gates.account_paused = False
    mock_fetch_gates.return_value = gates

    # Balance is above limit
    mock_prepaid.return_value = Decimal("100.00")

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")

    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    res = customer_live_execution_enable(mock_request, auth)
    
    assert res["status"] == "ok"
    assert res["live_trading_allowed"] is True
    assert res["tenant_id"] == "t-tenant-1"
    conn.execute.assert_called()


@patch("api_gateway.routes_commerce_customer._require_tenant_commercial_state")
@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.fetch_portal_identity_security")
def test_live_execution_enable_email_not_verified(
    mock_identity: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_verify: MagicMock,
    mock_flags: MagicMock,
    mock_settings: MagicMock,
    mock_require_state: MagicMock,
    mock_request: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = True
    mock_settings.return_value = settings

    mock_flags.return_value = (True, [])
    mock_verify.return_value = True
    mock_identity.return_value = None

    auth = _ctx(roles={"billing:read"}, tenant_id="t-tenant-1")
    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    with pytest.raises(HTTPException) as exc:
        customer_live_execution_enable(mock_request, auth)

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "EMAIL_NOT_VERIFIED"


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.verify_bitget_api_keys_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.tenant_has_active_live_commercial_contract")
@patch("api_gateway.routes_commerce_customer.fetch_prepaid_balance_list_usd")
@patch("api_gateway.routes_commerce_customer.fetch_tenant_modul_mate_gates")
@patch("api_gateway.routes_commerce_customer.record_gateway_audit_line")
def test_live_execution_enable_vault_mode_skips_global_env_flags(
    mock_audit: MagicMock,
    mock_fetch_gates: MagicMock,
    mock_prepaid: MagicMock,
    mock_has_contract: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_verify: MagicMock,
    mock_ready: MagicMock,
    mock_settings: MagicMock,
    mock_request: MagicMock,
) -> None:
    """Vault-Mandanten-Modus: globale BITGET_* duerfen leer sein."""
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.billing_min_balance_new_trade_usd = "50"
    settings.go_live_require_step_up = False
    settings.go_live_require_email_verified = False
    mock_settings.return_value = settings

    mock_ready.return_value = (True, [])
    mock_verify.return_value = True
    mock_has_contract.return_value = True
    gates = MagicMock()
    gates.account_suspended = False
    gates.account_paused = False
    mock_fetch_gates.return_value = gates
    mock_prepaid.return_value = Decimal("100.00")

    auth = _ctx(roles={"billing:read"}, tenant_id="t-vault-1")
    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    res = customer_live_execution_enable(mock_request, auth)

    assert res["status"] == "ok"
    mock_ready.assert_called_once_with("t-vault-1", demo=False)
    mock_verify.assert_called_once_with("t-vault-1")
