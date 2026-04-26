from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from shared_py.bitget import BitgetInstrumentMetadataService
from shared_py.bitget.catalog import BitgetInstrumentCatalog
from shared_py.bitget.instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentCatalogSnapshot,
)


class _FakeCatalog(BitgetInstrumentCatalog):
    def __init__(self, snapshot: BitgetInstrumentCatalogSnapshot) -> None:
        self._snapshot = snapshot

    def require_catalog(self, *, refresh_if_missing: bool = False):
        return self._snapshot

    def resolve(self, *, symbol: str, market_family: str | None = None, **kwargs):
        for entry in self._snapshot.entries:
            if entry.symbol == symbol and entry.market_family == (market_family or entry.market_family):
                return entry
        raise LookupError(symbol)

    def health_payload(self) -> dict[str, object]:
        return {"stale": False}


def _snapshot(entry: BitgetInstrumentCatalogEntry) -> BitgetInstrumentCatalogSnapshot:
    return BitgetInstrumentCatalogSnapshot(
        snapshot_id="snap-1",
        source_service="unit-test",
        refresh_reason="synthetic",
        status="ok",
        fetch_started_ts_ms=1,
        fetch_completed_ts_ms=int(time.time() * 1000),
        refreshed_families=[entry.market_family],
        entries=[entry],
    )


def test_metadata_preflight_rounds_to_tick_and_step() -> None:
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
        price_tick_size="0.5",
        quantity_step="0.01",
        quantity_min="0.01",
        quantity_max="10",
        leverage_max=20,
        funding_interval_hours=8,
    )
    svc = BitgetInstrumentMetadataService(_FakeCatalog(_snapshot(entry)))
    metadata = svc.resolve_for_trading(symbol="BTCUSDT", market_family="futures")
    preflight = svc.preflight_order(
        metadata=metadata,
        side="buy",
        order_type="limit",
        size="0.019",
        price="100.74",
        reduce_only=False,
        quote_size_order=False,
    )
    assert preflight.normalized_price == "100.5"
    assert preflight.normalized_size == "0.01"
    assert "price_rounded_to_tick" in preflight.reasons
    assert "size_rounded_to_step" in preflight.reasons


def test_metadata_preflight_flags_stale_catalog_row() -> None:
    old_ms = int(time.time() * 1000) - 7200_000
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
        price_tick_size="0.5",
        quantity_step="0.01",
        quantity_min="0.01",
        quantity_max="10",
        leverage_max=20,
        funding_interval_hours=8,
        refresh_ts_ms=old_ms,
    )
    svc = BitgetInstrumentMetadataService(_FakeCatalog(_snapshot(entry)))
    metadata = svc.resolve_for_trading(symbol="BTCUSDT", market_family="futures")
    preflight = svc.preflight_order(
        metadata=metadata,
        side="buy",
        order_type="limit",
        size="0.02",
        price="100",
        reduce_only=False,
        quote_size_order=False,
        max_metadata_age_sec=3600,
    )
    assert "catalog_metadata_stale" in preflight.reasons


def test_metadata_preflight_margin_coin_allowlist() -> None:
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
        price_tick_size="0.5",
        quantity_step="0.01",
        quantity_min="0.01",
        quantity_max="10",
        leverage_max=20,
        funding_interval_hours=8,
        supported_margin_coins=["USDT"],
    )
    svc = BitgetInstrumentMetadataService(_FakeCatalog(_snapshot(entry)))
    metadata = svc.resolve_for_trading(symbol="BTCUSDT", market_family="futures")
    bad = svc.preflight_order(
        metadata=metadata,
        side="buy",
        order_type="limit",
        size="0.02",
        price="100",
        reduce_only=False,
        quote_size_order=False,
        account_margin_coin="USDC",
    )
    assert "margin_coin_not_instrument_supported_list" in bad.reasons


def test_metadata_session_blocks_delivery_window() -> None:
    entry = BitgetInstrumentCatalogEntry(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="COIN-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="COIN-FUTURES",
        private_ws_inst_type="COIN-FUTURES",
        metadata_source="test",
        metadata_verified=True,
        trading_status="normal",
        trading_enabled=True,
        subscribe_enabled=True,
        price_tick_size="1",
        quantity_step="0.01",
        quantity_min="0.01",
        leverage_max=20,
        funding_interval_hours=8,
        session_metadata={
            "delivery_start_time": int(time.time() * 1000) - 1000,
        },
    )
    svc = BitgetInstrumentMetadataService(_FakeCatalog(_snapshot(entry)))
    metadata = svc.resolve_metadata(symbol="BTCUSDT", market_family="futures")
    assert metadata.session_state.open_new_positions_allowed_now is False
    assert "delivery_window_active" in metadata.session_state.reasons


def test_metadata_health_degraded_when_required_fields_missing() -> None:
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
    svc = BitgetInstrumentMetadataService(_FakeCatalog(_snapshot(entry)))
    health = svc.health_payload()
    assert health["status"] == "degraded"
    assert health["degraded_entry_count"] == 1
