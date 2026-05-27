from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (REPO_ROOT, GATEWAY_SRC, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.provider_ops_summary import (  # noqa: E402
    bitget_credentials_ready_for_tenant,
    bitget_env_hints_for_customer_portal,
)


@pytest.fixture(autouse=True)
def _clear_vault_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", raising=False)


def test_bitget_credentials_ready_uses_global_env_when_vault_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BITGET_API_KEY", "k")
    monkeypatch.setenv("BITGET_API_SECRET", "s")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "p")
    ok, gaps = bitget_credentials_ready_for_tenant("t-1", demo=False)
    assert ok is True
    assert gaps == []


@patch("api_gateway.provider_ops_summary.resolve_bitget_credentials_for_tenant")
def test_bitget_credentials_ready_vault_mode_skips_global_env(
    mock_resolve: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "true")
    mock_resolve.return_value = MagicMock()
    ok, gaps = bitget_credentials_ready_for_tenant("t-vault", demo=False)
    assert ok is True
    assert gaps == []
    mock_resolve.assert_called_once_with("t-vault")


@patch("api_gateway.provider_ops_summary.resolve_bitget_credentials_for_tenant")
def test_bitget_env_hints_vault_missing(
    mock_resolve: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "true")
    mock_resolve.return_value = None
    g = MagicMock()
    g.bitget_demo_enabled = False
    hints = bitget_env_hints_for_customer_portal(g, tenant_id="t-missing")
    assert hints["credentials_complete"] is False
    assert "bitget_tenant_vault_credentials_missing" in hints["gap_codes"]
    assert "Vault-Credentials" in hints["hint_public_de"]
