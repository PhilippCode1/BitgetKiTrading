from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    cs = str(candidate)
    if cs not in sys.path:
        sys.path.insert(0, cs)

pytest.importorskip("psycopg")
pytest.importorskip("fastapi")

from api_gateway.db_live_queries import (  # noqa: E402
    LIVE_STATE_CONTRACT_VERSION,
    build_live_state,
    compute_market_freshness_payload,
)

_MIN_GATEWAY_ENV: dict[str, str] = {
    "PRODUCTION": "false",
    "ADMIN_TOKEN": "unit_admin_token_for_tests_only________",
    "API_GATEWAY_URL": "http://127.0.0.1:8000",
    "DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/db",
    "DATABASE_URL_DOCKER": "postgresql://u:p@postgres:5432/db",
    "ENCRYPTION_KEY": "unit_encryption_key_32_chars_min______",
    "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
    "INTERNAL_API_KEY": "unit_internal_api_key_min_32_chars_x",
    "JWT_SECRET": "unit_jwt_secret_minimum_32_characters_",
    "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
    "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
    "POSTGRES_PASSWORD": "unit_postgres_pw",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "REDIS_URL_DOCKER": "redis://redis:6379/0",
    "SECRET_KEY": "unit_secret_key_minimum_32_characters",
}


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def _minimal_live_payload_empty_chart() -> dict:
    return {
        "live_state_contract_version": LIVE_STATE_CONTRACT_VERSION,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "server_ts_ms": 1_700_000_060_000,
        "candles": [],
        "latest_signal": None,
        "latest_feature": None,
        "structure_state": None,
        "latest_drawings": [],
        "latest_news": [],
        "paper_state": {
            "open_positions": [],
            "last_closed_trade": None,
            "unrealized_pnl_usdt": 0.0,
            "mark_price": None,
        },
        "online_drift": None,
        "data_lineage": [],
        "health": {"db": "ok", "redis": "skipped"},
        "market_freshness": {
            "status": "no_candles",
            "timeframe": "1m",
            "stale_warn_ms": 900_000,
            "candle": None,
            "ticker": None,
        },
        "demo_data_notice": {"show_banner": False, "reasons": []},
    }


def test_build_live_state_contract_when_db_unreachable() -> None:
    """Cold/db-error: stabile Keys, leere Kerzen, lineage-Liste, Frische-Block."""
    out = build_live_state(
        "",
        symbol="BTCUSDT",
        timeframe="1m",
        limit=10,
        stale_warn_ms=900_000,
        news_fixture_mode=False,
        bitget_demo_enabled=False,
    )
    assert out["live_state_contract_version"] == LIVE_STATE_CONTRACT_VERSION
    assert out["symbol"] == "BTCUSDT"
    assert out["timeframe"] == "1m"
    assert out["candles"] == []
    assert out["latest_signal"] is None
    assert isinstance(out["latest_drawings"], list)
    assert isinstance(out["latest_news"], list)
    assert isinstance(out["data_lineage"], list)
    assert out["health"]["db"] == "error"
    assert out["market_freshness"]["status"] in ("no_candles", "unknown_timeframe")
    assert out["paper_state"]["open_positions"] == []
    assert isinstance(out["demo_data_notice"], dict)


def test_compute_market_freshness_unknown_timeframe() -> None:
    mf = compute_market_freshness_payload(
        server_ts_ms=1_700_000_000_000,
        timeframe="9x",
        candle_meta=None,
        ticker_meta=None,
        stale_warn_ms=900_000,
    )
    assert mf["status"] == "unknown_timeframe"
    assert mf["candle"] is None


def test_compute_market_freshness_warm() -> None:
    tf_ms = 60_000
    server = 1_700_000_060_000
    aligned = (server // tf_ms) * tf_ms
    mf = compute_market_freshness_payload(
        server_ts_ms=server,
        timeframe="1m",
        candle_meta={
            "start_ts_ms": aligned,
            "ingest_ts_ms": server - 10_000,
        },
        ticker_meta={
            "ts_ms": server - 5_000,
            "ingest_ts_ms": server - 5_000,
            "last_pr": 42_000.0,
        },
        stale_warn_ms=900_000,
    )
    assert mf["status"] == "live"
    assert mf["candle"] is not None
    assert mf["ticker"] is not None
    assert mf["ticker"]["last_pr"] == 42_000.0


def test_live_state_http_envelope_empty_when_no_candles_and_signal() -> None:
    """GET /v1/live/state: GatewayReadStatus empty bei leerem Chart ohne Signal."""
    with (
        patch.dict(os.environ, _MIN_GATEWAY_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        with (
            patch(
                "api_gateway.routes_live.build_live_state",
                return_value=_minimal_live_payload_empty_chart(),
            ),
            patch(
                "api_gateway.routes_live.get_database_url",
                return_value="postgresql://u:p@127.0.0.1:5432/db",
            ),
        ):
            c = TestClient(app_module.app)
            r = c.get("/v1/live/state", params={"symbol": "BTCUSDT", "timeframe": "1m"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "empty"
    assert body["empty_state"] is True
    assert body["degradation_reason"] == "no_candles_and_signal"
    assert body["live_state_contract_version"] == LIVE_STATE_CONTRACT_VERSION


def test_compute_market_freshness_stale_bar_lag() -> None:
    tf_ms = 60_000
    server = 1_700_000_060_000
    aligned = (server // tf_ms) * tf_ms
    last_start = aligned - 6 * tf_ms
    mf = compute_market_freshness_payload(
        server_ts_ms=server,
        timeframe="1m",
        candle_meta={
            "start_ts_ms": last_start,
            "ingest_ts_ms": server - 5_000,
        },
        ticker_meta=None,
        stale_warn_ms=900_000,
    )
    assert mf["status"] == "dead"
