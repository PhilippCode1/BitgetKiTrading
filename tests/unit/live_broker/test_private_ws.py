from __future__ import annotations

import json

import pytest
from live_broker.private_ws.client import BitgetPrivateWsClient, PrivateWsClientStats
from live_broker.private_ws.models import NormalizedPrivateEvent

from shared_py.bitget.config import BitgetSettings


def test_normalized_private_event_from_ws_message_orders():
    # Example order event from Bitget docs
    msg = {
        "action": "snapshot",
        "arg": {"instType": "USDT-FUTURES", "instId": "default", "channel": "orders"},
        "data": [
            {
                "orderId": "13333333333333333333",
                "clientOid": "12354678990111",
                "status": "live",
                "instId": "ETHUSDT",
            }
        ],
        "ts": 1760461517285,
    }

    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "order"
    assert event.channel == "orders"
    assert event.inst_id == "default"
    assert event.inst_type == "USDT-FUTURES"
    assert event.action == "snapshot"
    assert event.exchange_ts_ms == 1760461517285
    assert len(event.data) == 1
    assert event.data[0]["orderId"] == "13333333333333333333"


def test_normalized_private_event_from_ws_message_account():
    # Example account event from Bitget docs
    msg = {
        "action": "snapshot",
        "arg": {"instType": "USDT-FUTURES", "channel": "account", "coin": "default"},
        "data": [{"marginCoin": "USDT", "available": "11.98545761"}],
        "ts": 1695717225146,
    }

    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "account"
    assert event.channel == "account"
    assert event.inst_id == "default"  # mapped from 'coin'
    assert event.inst_type == "USDT-FUTURES"
    assert event.exchange_ts_ms == 1695717225146
    assert len(event.data) == 1
    assert event.data[0]["available"] == "11.98545761"


def test_normalized_private_event_from_ws_message_unknown():
    msg = {"arg": {"channel": "weird_channel"}, "data": [], "ts": "12345678"}
    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "unknown"
    assert event.channel == "weird_channel"
    assert event.exchange_ts_ms == 12345678


def test_normalized_private_event_fill_channel_maps_to_fill_type():
    msg = {
        "action": "update",
        "arg": {
            "instType": "USDT-FUTURES",
            "instId": "default",
            "channel": "fill",
        },
        "data": [
            {
                "orderId": "o1",
                "tradeId": "t1",
                "baseVolume": "0.05",
            }
        ],
        "ts": 2_000_000_000_000,
    }
    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "fill"
    assert event.channel == "fill"
    assert event.action == "update"
    assert event.data[0]["tradeId"] == "t1"


def test_normalized_private_event_positions_channel_maps_to_position_type():
    msg = {
        "action": "snapshot",
        "arg": {
            "instType": "USDT-FUTURES",
            "instId": "default",
            "channel": "positions",
        },
        "data": [{"instId": "BTCUSDT", "holdSide": "long", "total": "0.02"}],
        "ts": 3,
    }
    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "position"
    assert event.channel == "positions"
    assert event.data[0]["holdSide"] == "long"


def test_normalized_private_event_invalid_ts_falls_back_to_monotonic_range(monkeypatch):
    import live_broker.private_ws.models as ws_models

    monkeypatch.setattr(ws_models.time, "time", lambda: 100.0)
    msg = {"arg": {"channel": "orders"}, "data": [], "ts": "not-a-number"}
    event = NormalizedPrivateEvent.from_ws_message(msg)
    assert event.event_type == "order"
    assert event.exchange_ts_ms == 100_000


class MockWebsocket:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.sent: list[str] = []
        self._closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self.responses:
            raise TimeoutError()
        return self.responses.pop(0)

    async def close(self) -> None:
        self._closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.responses:
            # End the loop
            raise StopAsyncIteration
        return self.responses.pop(0)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_ws_client_login_success(monkeypatch: pytest.MonkeyPatch):
    # BaseSettings: OS-ENV schlaegt model_validate-Input; Werte explizit setzen.
    monkeypatch.setenv("BITGET_API_KEY", "test_key")
    monkeypatch.setenv("BITGET_API_SECRET", "test_secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "test_passphrase")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    settings = BitgetSettings.model_validate(
        {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "api_passphrase": "test_passphrase",
        }
    )
    stats = PrivateWsClientStats()

    client = BitgetPrivateWsClient(
        bitget_settings=settings,
        stats=stats,
        ping_interval_sec=0.1,
    )

    mock_ws = MockWebsocket([json.dumps({"event": "login", "code": 0})])
    client._websocket = mock_ws

    await client._login()
    assert len(mock_ws.sent) == 1
    login_req = json.loads(mock_ws.sent[0])
    assert login_req["op"] == "login"
    assert login_req["args"][0]["apiKey"] == "test_key"
    assert "sign" in login_req["args"][0]


@pytest.mark.anyio
async def test_ws_client_login_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BITGET_API_KEY", "test_key")
    monkeypatch.setenv("BITGET_API_SECRET", "test_secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "test_passphrase")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    settings = BitgetSettings.model_validate(
        {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "api_passphrase": "test_passphrase",
        }
    )
    stats = PrivateWsClientStats()

    client = BitgetPrivateWsClient(
        bitget_settings=settings,
        stats=stats,
    )

    mock_ws = MockWebsocket(
        [json.dumps({"event": "error", "code": 40001, "msg": "auth failed"})]
    )
    client._websocket = mock_ws

    with pytest.raises(ValueError, match="WS Login failed"):
        await client._login()


@pytest.mark.anyio
async def test_ws_client_receive_loop(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BITGET_API_KEY", "test_key")
    monkeypatch.setenv("BITGET_API_SECRET", "test_secret")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "test_passphrase")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    settings = BitgetSettings.model_validate(
        {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "api_passphrase": "test_passphrase",
        }
    )
    stats = PrivateWsClientStats()

    received_events: list[NormalizedPrivateEvent] = []

    async def _handler(event: NormalizedPrivateEvent):
        received_events.append(event)

    client = BitgetPrivateWsClient(
        bitget_settings=settings, stats=stats, message_handlers=[_handler]
    )

    # Provide a pong, a subscribe ack, and a valid event
    mock_ws = MockWebsocket(
        [
            "pong",
            json.dumps({"event": "subscribe", "arg": {"channel": "orders"}}),
            json.dumps(
                {
                    "action": "snapshot",
                    "arg": {
                        "channel": "orders",
                        "instType": "USDT-FUTURES",
                        "instId": "default",
                    },
                    "data": [{"orderId": "123"}],
                    "ts": 1000000,
                }
            ),
        ]
    )
    client._websocket = mock_ws

    await client._receive_loop()

    assert stats.pong_count == 1
    assert stats.received_events == 1
    assert len(received_events) == 1
    assert received_events[0].event_type == "order"
