from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetSettings,
    UnknownInstrumentError,
)
from shared_py.bitget.discovery import BitgetMarketDiscoveryClient
from shared_py.bitget.instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentCatalogSnapshot,
)


def test_catalog_resolve_uses_canonical_entry() -> None:
    settings = BitgetSettings(symbol="BTCUSDT")
    catalog = BitgetInstrumentCatalog(
        bitget_settings=settings,
        database_url="postgresql://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
        source_service="unit-test",
    )
    entry = BitgetInstrumentCatalogEntry(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="test",
        metadata_verified=True,
        trading_status="normal",
        trading_enabled=True,
        subscribe_enabled=True,
    )
    catalog._memory_snapshot = BitgetInstrumentCatalogSnapshot(
        snapshot_id="snap-1",
        source_service="unit-test",
        refresh_reason="synthetic",
        status="ok",
        fetch_started_ts_ms=1,
        fetch_completed_ts_ms=int(time.time() * 1000),
        refreshed_families=["futures"],
        entries=[entry],
    )
    resolved = catalog.resolve(
        symbol="BTCUSDT",
        market_family="futures",
        product_type="USDT-FUTURES",
    )
    assert resolved.canonical_instrument_id == "bitget:futures:USDT-FUTURES:BTCUSDT"


def test_catalog_unknown_instrument_raises() -> None:
    settings = BitgetSettings(symbol="BTCUSDT")
    catalog = BitgetInstrumentCatalog(
        bitget_settings=settings,
        database_url="postgresql://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
        source_service="unit-test",
    )
    catalog._memory_snapshot = BitgetInstrumentCatalogSnapshot(
        snapshot_id="snap-1",
        source_service="unit-test",
        refresh_reason="synthetic",
        status="ok",
        fetch_started_ts_ms=1,
        fetch_completed_ts_ms=int(time.time() * 1000),
        refreshed_families=["futures"],
        entries=[],
    )
    with pytest.raises(UnknownInstrumentError):
        catalog.resolve(symbol="ETHUSDT", market_family="spot")


def test_discovery_catalog_snapshot_builds_futures_and_spot(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = BitgetSettings(symbol="BTCUSDT")
    discovery = BitgetMarketDiscoveryClient(settings)

    def fake_public(path: str, *, params: dict[str, str]):
        if path == "/api/v2/spot/public/symbols":
            return {
                "code": "00000",
                "data": [
                    {
                        "symbol": "BTCUSDT",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "pricePrecision": "2",
                        "quantityPrecision": "4",
                        "quotePrecision": "2",
                        "minTradeAmount": "0.0001",
                        "minTradeUSDT": "5",
                        "status": "online",
                    }
                ],
            }
        return {
            "code": "00000",
            "data": [
                {
                    "symbol": "BTCUSDT",
                    "productType": params["productType"],
                    "baseCoin": "BTC",
                    "quoteCoin": "USDT",
                    "supportMarginCoins": ["USDT"],
                    "minTradeNum": "0.001",
                    "minTradeUSDT": "5",
                    "priceEndStep": "0.1",
                    "sizeMultiplier": "0.001",
                    "pricePlace": "1",
                    "volumePlace": "3",
                    "symbolStatus": "normal",
                    "minLever": "1",
                    "maxLever": "50",
                    "symbolType": "perpetual",
                }
            ],
        }

    def fake_private(path: str, *, params: dict[str, str]):
        return {"code": "00000", "data": []}

    monkeypatch.setattr(discovery, "_public_json", fake_public)
    monkeypatch.setattr(discovery, "_private_json", fake_private)

    snapshot = discovery.discover_catalog_snapshot(
        source_service="unit-test",
        refresh_reason="test",
    )
    assert snapshot.status == "ok"
    assert "spot" in snapshot.refreshed_families
    assert "futures" in snapshot.refreshed_families
    assert any(entry.market_family == "spot" for entry in snapshot.entries)
    assert any(
        entry.market_family == "futures" and entry.product_type == "USDT-FUTURES"
        for entry in snapshot.entries
    )
    assert any(
        row.market_family == "spot" and row.analytics_eligible and row.execution_disabled is False
        for row in snapshot.capability_matrix
    )
    assert any(
        row.market_family == "futures"
        and row.product_type == "USDT-FUTURES"
        and row.live_execution_enabled
        and row.supports_shorting
        for row in snapshot.capability_matrix
    )
    assert any(
        row.market_family == "margin"
        and row.margin_account_mode == "crossed"
        and row.inventory_visible is False
        for row in snapshot.capability_matrix
    )
