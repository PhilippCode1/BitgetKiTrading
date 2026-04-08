from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from api_gateway.db_market_universe_queries import fetch_market_universe_status


class _FakeCursor:
    def __init__(self, *, one: dict[str, object] | None = None, many: list[dict[str, object]] | None = None):
        self._one = one
        self._many = many or []

    def fetchone(self) -> dict[str, object] | None:
        return self._one

    def fetchall(self) -> list[dict[str, object]]:
        return self._many


class _FakeConn:
    def __init__(self, *, snapshot_row: dict[str, object] | None, entry_rows: list[dict[str, object]]):
        self._snapshot_row = snapshot_row
        self._entry_rows = entry_rows

    def execute(self, sql: str, _params: object | None = None) -> _FakeCursor:
        if "FROM app.instrument_catalog_snapshots" in sql:
            return _FakeCursor(one=self._snapshot_row)
        if "FROM app.instrument_catalog_entries" in sql:
            return _FakeCursor(many=self._entry_rows)
        return _FakeCursor()


def test_fetch_market_universe_status_returns_matrix_and_registry() -> None:
    snapshot_row = {
        "snapshot_id": "00000000-0000-0000-0000-000000000001",
        "source_service": "market-stream",
        "refresh_reason": "unit",
        "status": "ok",
        "fetch_started_ts_ms": 1,
        "fetch_completed_ts_ms": 2,
        "refreshed_families_json": ["spot", "margin", "futures"],
        "counts_json": {"futures": 1},
        "capability_matrix_json": [
            {
                "schema_version": "bitget-market-universe-v1",
                "venue": "bitget",
                "market_family": "futures",
                "product_type": "USDT-FUTURES",
                "margin_account_mode": "isolated",
                "category_key": "bitget:futures:USDT-FUTURES",
                "metadata_source": "/api/v2/mix/market/contracts",
                "metadata_verified": True,
                "inventory_visible": True,
                "analytics_eligible": True,
                "paper_shadow_eligible": True,
                "live_execution_enabled": True,
                "execution_disabled": False,
                "supports_funding": True,
                "supports_open_interest": True,
                "supports_long_short": True,
                "supports_shorting": True,
                "supports_reduce_only": True,
                "supports_leverage": True,
                "uses_spot_public_market_data": False,
                "instrument_count": 1,
                "tradeable_instrument_count": 1,
                "subscribable_instrument_count": 1,
                "metadata_verified_count": 1,
                "sample_symbols": ["BTCUSDT"],
                "reasons": [],
            }
        ],
        "warnings_json": [],
        "errors_json": [],
    }
    entry_rows = [
        {
            "schema_version": "bitget-market-universe-v1",
            "canonical_instrument_id": "bitget:futures:USDT-FUTURES:BTCUSDT",
            "snapshot_id": "00000000-0000-0000-0000-000000000001",
            "venue": "bitget",
            "market_family": "futures",
            "symbol": "BTCUSDT",
            "symbol_aliases_json": ["BTCUSDT"],
            "category_key": "bitget:futures:USDT-FUTURES",
            "product_type": "USDT-FUTURES",
            "margin_account_mode": "isolated",
            "margin_coin": "USDT",
            "base_coin": "BTC",
            "quote_coin": "USDT",
            "settle_coin": "USDT",
            "public_ws_inst_type": "USDT-FUTURES",
            "private_ws_inst_type": "USDT-FUTURES",
            "metadata_source": "/api/v2/mix/market/contracts",
            "metadata_verified": True,
            "status": "normal",
            "inventory_visible": True,
            "analytics_eligible": True,
            "paper_shadow_eligible": True,
            "live_execution_enabled": True,
            "execution_disabled": False,
            "supports_funding": True,
            "supports_open_interest": True,
            "supports_long_short": True,
            "supports_shorting": True,
            "supports_reduce_only": True,
            "supports_leverage": True,
            "uses_spot_public_market_data": False,
            "price_tick_size": "0.1",
            "quantity_step": "0.001",
            "quantity_min": "0.001",
            "quantity_max": "100",
            "market_order_quantity_max": "50",
            "min_notional_quote": "5",
            "price_precision": 1,
            "quantity_precision": 3,
            "quote_precision": 2,
            "leverage_min": 1,
            "leverage_max": 50,
            "funding_interval_hours": 8,
            "symbol_type": "perpetual",
            "supported_margin_coins_json": ["USDT"],
            "trading_status": "normal",
            "trading_enabled": True,
            "subscribe_enabled": True,
            "session_metadata_json": {"schedule": "24x7"},
            "refresh_ts_ms": 2,
            "raw_metadata_json": {"symbol": "BTCUSDT"},
        }
    ]

    payload = fetch_market_universe_status(
        _FakeConn(snapshot_row=snapshot_row, entry_rows=entry_rows),
        configuration_snapshot={
            "market_families": ["spot", "margin", "futures"],
            "universe_symbols": ["BTCUSDT"],
            "watchlist_symbols": ["BTCUSDT"],
            "feature_scope": {"symbols": ["BTCUSDT"], "timeframes": ["5m"]},
            "signal_scope_symbols": ["BTCUSDT"],
            "family_defaults": {},
            "live_allowlists": {
                "symbols": ["BTCUSDT"],
                "market_families": ["futures"],
                "product_types": ["USDT-FUTURES"],
            },
            "catalog_policy": {
                "refresh_interval_sec": 300,
                "cache_ttl_sec": 900,
                "max_stale_sec": 1800,
                "unknown_instrument_action": "no_trade_no_subscribe",
            },
        },
    )

    assert payload["schema_version"] == "bitget-market-universe-v1"
    assert payload["snapshot"]["status"] == "ok"
    assert payload["categories"][0]["category_key"] == "bitget:futures:USDT-FUTURES"
    assert payload["categories"][0]["supports_shorting"] is True
    assert payload["instruments"][0]["canonical_instrument_id"] == "bitget:futures:USDT-FUTURES:BTCUSDT"
    assert payload["instruments"][0]["live_execution_enabled"] is True
    assert payload["summary"]["live_execution_enabled_category_count"] == 1
