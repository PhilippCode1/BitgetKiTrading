"""Catalog snapshot: Postgres-Inhalt muss Vorrang vor Redis haben (kein Fixture/Cache-Drift)."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from shared_py.bitget.catalog import BitgetInstrumentCatalog
from shared_py.bitget.config import BitgetSettings
from shared_py.bitget.instruments import BitgetInstrumentCatalogSnapshot


def _fresh_snapshot(snapshot_id: str) -> BitgetInstrumentCatalogSnapshot:
    ts = int(time.time() * 1000)
    return BitgetInstrumentCatalogSnapshot(
        snapshot_id=snapshot_id,
        source_service="test",
        refresh_reason="test",
        fetch_started_ts_ms=ts,
        fetch_completed_ts_ms=ts,
        entries=[],
    )


def test_get_snapshot_prefers_database_over_redis_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    db_snap = _fresh_snapshot("from-postgres")
    redis_snap = _fresh_snapshot("from-redis")
    settings = BitgetSettings(
        database_url="postgresql://127.0.0.1:1/catalog_db_precedence",
        redis_url="redis://127.0.0.1:6379/0",
    )
    catalog = BitgetInstrumentCatalog(
        bitget_settings=settings,
        database_url=settings.database_url,
        redis_url=settings.redis_url,
        source_service="test",
    )
    with (
        patch.object(
            BitgetInstrumentCatalog, "_load_db_snapshot", return_value=db_snap
        ) as load_db,
        patch.object(
            BitgetInstrumentCatalog, "_load_cached_snapshot", return_value=redis_snap
        ) as load_cache,
        patch.object(BitgetInstrumentCatalog, "_cache_snapshot") as write_cache,
    ):
        out = catalog.get_snapshot()
    load_db.assert_called_once()
    # Redis wird nur benoetigt, wenn kein brauchbarer DB-Snapshot da ist
    load_cache.assert_not_called()
    assert out is not None
    assert out.snapshot_id == "from-postgres"
    write_cache.assert_called_once()
    call_snap = write_cache.call_args[0][0]
    assert call_snap.snapshot_id == "from-postgres"
