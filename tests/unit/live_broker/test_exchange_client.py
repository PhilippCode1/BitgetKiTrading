from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from live_broker.config import LiveBrokerSettings
from live_broker.exchange_client import BitgetExchangeClient
from live_broker.execution.models import ExecutionIntentRequest


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("BITGET_REST_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("BITGET_WS_PRIVATE_URL", "wss://example.invalid/ws")
    monkeypatch.setenv("BITGET_SYMBOL", "ETHUSDT")
    monkeypatch.setenv("BITGET_MARKET_FAMILY", "futures")
    monkeypatch.setenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES")
    # OS-ENV schlaegt .env.local; leere Werte verhindern echte Keys aus der Datei.
    monkeypatch.setenv("BITGET_API_KEY", "")
    monkeypatch.setenv("BITGET_API_SECRET", "")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "")
    return LiveBrokerSettings()


def test_describe_and_private_api_configured(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    d = client.describe()
    assert "effective_rest_base_url" in d
    ok, detail = client.private_api_configured()
    assert ok is False
    assert "missing" in detail


def test_private_api_configured_ok(
    settings: LiveBrokerSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BITGET_API_KEY", "k")
    monkeypatch.setenv("BITGET_API_SECRET", "s")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "p")
    s = LiveBrokerSettings()
    client = BitgetExchangeClient(s)
    ok, detail = client.private_api_configured()
    assert ok is True
    assert detail == "ok"


def test_get_market_snapshot_list_payload(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"price": "50000", "markPrice": "49990"}],
        "requestTime": 1,
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("live_broker.exchange_client.httpx.Client", return_value=mock_client):
        out = client.get_market_snapshot("BTCUSDT")
    assert out["symbol"] == "BTCUSDT"
    assert out["last_price"] == "50000"
    assert out["mark_price"] == "49990"


def test_get_market_snapshot_dict_payload(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"lastPr": "1", "indexPrice": "2"}}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("live_broker.exchange_client.httpx.Client", return_value=mock_client):
        out = client.get_market_snapshot("ETHUSDT")
    assert out["last_price"] == "1"
    assert out["index_price"] == "2"


def test_get_market_snapshot_invalid_data_raises(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("live_broker.exchange_client.httpx.Client", return_value=mock_client):
        with pytest.raises(ValueError, match="fehlt"):
            client.get_market_snapshot("BTCUSDT")


def test_build_order_preview(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    intent = ExecutionIntentRequest(
        symbol="BTCUSDT",
        direction="long",
        order_type="market",
        qty_base="0.01",
        leverage=7,
        entry_price="100",
        stop_loss="99",
        take_profit="101",
        requested_runtime_mode="shadow",
    )
    prev = client.build_order_preview(intent)
    assert prev["side"] == "buy"
    intent2 = intent.model_copy(update={"direction": "short"})
    assert client.build_order_preview(intent2)["side"] == "sell"


def test_probe_exchange_success_and_failure(settings: LiveBrokerSettings) -> None:
    client = BitgetExchangeClient(settings)
    with patch.object(
        client,
        "get_market_snapshot",
        return_value={"symbol": "BTCUSDT", "last_price": "1"},
    ):
        probe = client.probe_exchange()
    assert probe["public_api_ok"] is True

    with patch.object(client, "get_market_snapshot", side_effect=RuntimeError("net")):
        probe2 = client.probe_exchange()
    assert probe2["public_api_ok"] is False
    assert "net" in probe2["public_detail"]
