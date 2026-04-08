"""REST-Snapshot-Catchup: Payload-Parsing und Repo-Schreibvorgänge (Recovery / Reconnect)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.reconcile.rest_catchup import run_rest_snapshot_catchup


class _FakePrivate:
    def __init__(self, orders_payload: dict, positions_payload: dict) -> None:
        self._orders_payload = orders_payload
        self._positions_payload = positions_payload

    def list_orders_pending(self, *, priority: bool = False) -> SimpleNamespace:
        return SimpleNamespace(payload=self._orders_payload)

    def list_all_positions(self, *, priority: bool = False) -> SimpleNamespace:
        return SimpleNamespace(payload=self._positions_payload)


class _FakeRepo:
    def __init__(self) -> None:
        self.recorded: list[dict] = []

    def record_exchange_snapshot(self, row: dict) -> None:
        self.recorded.append(row)


def _settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("EXECUTION_MODE", "shadow"),
        ("SHADOW_TRADE_ENABLE", "true"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("BITGET_SYMBOL", "ETHUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("BITGET_API_KEY", "k"),
        ("BITGET_API_SECRET", "s"),
        ("BITGET_API_PASSPHRASE", "p"),
    ):
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def test_rest_catchup_writes_orders_and_positions_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    private = _FakePrivate(
        orders_payload={
            "data": {
                "entrustedList": [
                    {"instId": "BTCUSDT", "orderId": "1"},
                    {"instId": "ETHUSDT", "orderId": "2"},
                ]
            }
        },
        positions_payload={"data": {"list": [{"instId": "BTCUSDT", "holdSide": "long"}]}},
    )
    out = run_rest_snapshot_catchup(settings, repo, private, reason="test")
    assert out["ok"] is True
    assert out["order_snapshot_rows"] == 2
    assert out["position_snapshot_rows"] == 1

    orders_rows = [r for r in repo.recorded if r["snapshot_type"] == "orders"]
    pos_rows = [r for r in repo.recorded if r["snapshot_type"] == "positions"]
    assert len(orders_rows) == 2
    assert len(pos_rows) == 1
    syms_o = {r["symbol"] for r in orders_rows}
    assert syms_o == {"BTCUSDT", "ETHUSDT"}
    assert pos_rows[0]["symbol"] == "BTCUSDT"
    for r in repo.recorded:
        raw = r["raw_data"]
        assert raw["source"] == "rest_catchup"
        assert raw["reason"] == "test"
        assert raw["action"] == "snapshot"


def test_rest_catchup_empty_lists_still_record_symbol_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    private = _FakePrivate(
        orders_payload={"data": {}},
        positions_payload={"data": {}},
    )
    run_rest_snapshot_catchup(settings, repo, private, reason="empty")
    assert len(repo.recorded) == 2
    assert {r["snapshot_type"] for r in repo.recorded} == {"orders", "positions"}
    sym = str(settings.symbol)
    assert all(r["symbol"] == sym for r in repo.recorded)


def test_rest_catchup_skips_when_private_runtime_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Shadow/Live-Order-Pfad ist private_exchange_access_enabled false (kein Catchup)."""
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("EXECUTION_MODE", "paper"),
        ("SHADOW_TRADE_ENABLE", "false"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("LIVE_TRADE_ENABLE", "false"),
        ("BITGET_MARGIN_COIN", "USDT"),
    ):
        monkeypatch.setenv(k, v)
    settings = LiveBrokerSettings()
    assert settings.private_exchange_access_enabled is False
    repo = _FakeRepo()
    private = _FakePrivate(orders_payload={"data": []}, positions_payload={"data": []})
    out = run_rest_snapshot_catchup(settings, repo, private, reason="x")
    assert out.get("skipped") is True
    assert repo.recorded == []
