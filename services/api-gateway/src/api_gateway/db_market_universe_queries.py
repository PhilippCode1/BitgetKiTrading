from __future__ import annotations

import json
from typing import Any

import psycopg

from shared_py.bitget.instruments import (
    MARKET_UNIVERSE_SCHEMA_VERSION,
    BitgetInstrumentCatalogEntry,
    BitgetMarketCapabilityMatrixRow,
    build_capability_matrix,
)


def _j(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _entry_from_row(row: dict[str, Any]) -> BitgetInstrumentCatalogEntry:
    return BitgetInstrumentCatalogEntry.model_validate(
        {
            **row,
            "symbol_aliases": list(row.get("symbol_aliases_json") or []),
            "supported_margin_coins": list(row.get("supported_margin_coins_json") or []),
            "session_metadata": dict(row.get("session_metadata_json") or {}),
            "raw_metadata": dict(row.get("raw_metadata_json") or {}),
        }
    )


def _snapshot_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "snapshot_id": str(row["snapshot_id"]),
        "status": str(row["status"]),
        "source_service": str(row["source_service"]),
        "refresh_reason": str(row["refresh_reason"]),
        "fetch_started_ts_ms": int(row["fetch_started_ts_ms"]),
        "fetch_completed_ts_ms": int(row["fetch_completed_ts_ms"])
        if row.get("fetch_completed_ts_ms") is not None
        else None,
        "refreshed_families": list(row.get("refreshed_families_json") or []),
        "counts_by_family": dict(row.get("counts_json") or {}),
        "warnings": list(row.get("warnings_json") or []),
        "errors": list(row.get("errors_json") or []),
    }


def _summary(
    *,
    categories: list[BitgetMarketCapabilityMatrixRow],
    instruments: list[BitgetInstrumentCatalogEntry],
) -> dict[str, Any]:
    return {
        "category_count": len(categories),
        "instrument_count": len(instruments),
        "inventory_visible_category_count": sum(1 for item in categories if item.inventory_visible),
        "analytics_eligible_category_count": sum(1 for item in categories if item.analytics_eligible),
        "paper_shadow_eligible_category_count": sum(
            1 for item in categories if item.paper_shadow_eligible
        ),
        "live_execution_enabled_category_count": sum(
            1 for item in categories if item.live_execution_enabled
        ),
        "execution_disabled_category_count": sum(1 for item in categories if item.execution_disabled),
        "inventory_visible_instrument_count": sum(1 for item in instruments if item.inventory_visible),
        "analytics_eligible_instrument_count": sum(
            1 for item in instruments if item.analytics_eligible
        ),
        "paper_shadow_eligible_instrument_count": sum(
            1 for item in instruments if item.paper_shadow_eligible
        ),
        "live_execution_enabled_instrument_count": sum(
            1 for item in instruments if item.live_execution_enabled
        ),
        "execution_disabled_instrument_count": sum(
            1 for item in instruments if item.execution_disabled
        ),
    }


def fetch_market_universe_status(
    conn: psycopg.Connection[Any],
    *,
    configuration_snapshot: dict[str, Any],
) -> dict[str, Any]:
    snapshot_row_raw = conn.execute(
        """
        SELECT snapshot_id, source_service, refresh_reason, status,
               fetch_started_ts_ms, fetch_completed_ts_ms,
               refreshed_families_json, counts_json, capability_matrix_json,
               warnings_json, errors_json
        FROM app.instrument_catalog_snapshots
        ORDER BY fetch_completed_ts_ms DESC NULLS LAST, fetch_started_ts_ms DESC
        LIMIT 1
        """
    ).fetchone()
    snapshot_row = dict(snapshot_row_raw) if snapshot_row_raw is not None else None
    entry_rows = conn.execute(
        """
        SELECT *
        FROM app.instrument_catalog_entries
        ORDER BY market_family, category_key NULLS LAST, product_type NULLS LAST, symbol
        """
    ).fetchall()
    instruments = [_entry_from_row(dict(row)) for row in entry_rows]
    categories_payload = []
    if snapshot_row is not None:
        categories_payload = [
            item
            for item in list(_j(snapshot_row.get("capability_matrix_json")) or [])
            if isinstance(item, dict)
        ]
    categories = (
        [BitgetMarketCapabilityMatrixRow.model_validate(item) for item in categories_payload]
        if categories_payload
        else build_capability_matrix(instruments)
    )
    return {
        "schema_version": MARKET_UNIVERSE_SCHEMA_VERSION,
        "configuration": configuration_snapshot,
        "snapshot": _snapshot_payload(snapshot_row),
        "summary": _summary(categories=categories, instruments=instruments),
        "categories": [item.model_dump(mode="json") for item in categories],
        "instruments": [item.model_dump(mode="json") for item in instruments],
    }
