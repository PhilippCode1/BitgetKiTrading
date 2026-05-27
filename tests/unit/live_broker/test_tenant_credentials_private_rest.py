"""Tenant-Credentials im Live-Broker private REST."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError
from live_broker.tenant_credentials import tenant_credentials_scope
from shared_py.tenant_exchange_credentials import BitgetCredentialBundle


def _minimal_settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://t:t@127.0.0.1:5432/t"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("BITGET_SYMBOL", "BTCUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("LIVE_BROKER_BASE_URL", "https://example.invalid"),
    ):
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def test_tenant_scope_overrides_global_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _minimal_settings(monkeypatch)
    client = BitgetPrivateRestClient(settings, transport=MagicMock())
    bundle = BitgetCredentialBundle(
        api_key="tenant-key",
        api_secret="tenant-secret",
        api_passphrase="tenant-pass",
        source="vault_tenant",
    )
    with patch(
        "live_broker.tenant_credentials.resolve_bundle_for_trace",
        return_value=bundle,
    ):
        with tenant_credentials_scope(settings, {"tenant_id": "t-tenant-1"}):
            with patch.object(client, "sync_server_time", return_value={}):
                with patch.object(client, "_reject_if_clock_skew_too_large"):
                    with patch.object(client, "_build_client") as mock_build:
                        mock_http = MagicMock()
                        mock_build.return_value.__enter__.return_value = mock_http
                        mock_http.request.return_value = MagicMock(
                            status_code=200,
                            json=lambda: {"code": "00000", "data": {}},
                        )
                        with patch(
                            "live_broker.private_rest.build_private_rest_headers",
                            return_value={"ACCESS-KEY": "tenant-key"},
                        ) as mock_headers:
                            client.place_order({"symbol": "BTCUSDT", "size": "1"})
    mock_headers.assert_called()
    assert mock_headers.call_args.kwargs["api_key"] == "tenant-key"


def test_vault_required_fail_closed_without_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _minimal_settings(monkeypatch)
    monkeypatch.setenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "true")
    with patch(
        "live_broker.tenant_credentials.resolve_bundle_for_trace",
        return_value=None,
    ):
        with pytest.raises(BitgetRestError, match="tenant_exchange_credentials"):
            with tenant_credentials_scope(settings, {"tenant_id": "t-tenant-1"}):
                pass
