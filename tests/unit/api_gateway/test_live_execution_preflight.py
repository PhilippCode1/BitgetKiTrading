from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (REPO_ROOT, GATEWAY_SRC, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.auth import GatewayAuthContext
from api_gateway.routes_commerce_customer import customer_live_execution_preflight


def _ctx(*, tenant_id: str = "t-tenant-1") -> GatewayAuthContext:
    ctx = GatewayAuthContext(
        actor="u1",
        auth_method="jwt",
        roles=frozenset({"billing:read"}),
        tenant_id=tenant_id,
    )
    object.__setattr__(ctx, "portal_roles", frozenset({"customer"}))
    return ctx


@patch("api_gateway.routes_commerce_customer.get_gateway_settings")
@patch("api_gateway.routes_commerce_customer.bitget_credentials_ready_for_tenant")
@patch("api_gateway.routes_commerce_customer.get_database_url")
@patch("api_gateway.routes_commerce_customer.gateway_psycopg")
@patch("api_gateway.routes_commerce_customer.tenant_has_active_live_commercial_contract")
@patch("api_gateway.routes_commerce_customer.fetch_prepaid_balance_list_usd")
@patch("api_gateway.routes_commerce_customer.fetch_tenant_modul_mate_gates")
def test_live_execution_preflight_reports_blockers(
    mock_fetch_gates: MagicMock,
    mock_prepaid: MagicMock,
    mock_has_contract: MagicMock,
    mock_psycopg: MagicMock,
    mock_db_url: MagicMock,
    mock_ready: MagicMock,
    mock_settings: MagicMock,
) -> None:
    settings = MagicMock()
    settings.commercial_enabled = True
    settings.bitget_demo_enabled = False
    settings.billing_min_balance_new_trade_usd = "50"
    settings.go_live_require_email_verified = True
    mock_settings.return_value = settings

    mock_ready.return_value = (False, ["bitget_tenant_vault_credentials_missing"])
    mock_has_contract.return_value = False
    mock_prepaid.return_value = Decimal("10.00")
    gates = MagicMock()
    gates.account_paused = False
    gates.account_suspended = False
    mock_fetch_gates.return_value = gates

    conn = MagicMock()
    mock_psycopg.return_value.__enter__.return_value = conn

    with patch(
        "api_gateway.routes_commerce_customer.fetch_portal_identity_security",
        return_value=None,
    ):
        with patch(
            "api_gateway.go_live_step_up.go_live_step_up_required",
            return_value=True,
        ):
            result = customer_live_execution_preflight(_ctx())

    assert result["ready"] is False
    assert result["step_up_required"] is True
    assert "MISSING_API_KEYS" in result["blockers"]
    assert "CONTRACT_NOT_SIGNED" in result["blockers"]
    assert "INSUFFICIENT_BALANCE" in result["blockers"]
    assert "EMAIL_NOT_VERIFIED" in result["blockers"]
