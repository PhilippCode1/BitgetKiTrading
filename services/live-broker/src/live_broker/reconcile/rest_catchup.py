"""REST-basierte Snapshots nach WS-Reconnect oder Start — ergaenzt WS-Incremental-Feeds."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings
    from live_broker.persistence.repo import LiveBrokerRepository
    from live_broker.private_rest import BitgetPrivateRestClient

logger = logging.getLogger("live_broker.reconcile.rest_catchup")


def _orders_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [dict(x) for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("entrustedList", "orderList", "orders", "list"):
            raw = data.get(key)
            if isinstance(raw, list):
                return [dict(x) for x in raw if isinstance(x, dict)]
    return []


def _positions_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [dict(x) for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("list", "positions", "dataList"):
            raw = data.get(key)
            if isinstance(raw, list):
                return [dict(x) for x in raw if isinstance(x, dict)]
    return []


def run_rest_snapshot_catchup(
    settings: "LiveBrokerSettings",
    repo: "LiveBrokerRepository",
    private: "BitgetPrivateRestClient",
    *,
    reason: str,
    reconcile_run_id: str | None = None,
) -> dict[str, Any]:
    if not settings.private_exchange_access_enabled:
        return {"ok": True, "skipped": True, "reason": "private_exchange_access_disabled"}
    ingest_ts_ms = int(time.time() * 1000)
    rows_orders = 0
    rows_positions = 0
    try:
        oresp = private.list_orders_pending(priority=True)
        oitems = _orders_items_from_payload(oresp.payload)
        grouped_o: dict[str, list[dict[str, Any]]] = {}
        for it in oitems:
            sym = str(it.get("instId") or it.get("symbol") or settings.symbol or "default")
            grouped_o.setdefault(sym, []).append(it)
        if not grouped_o:
            grouped_o[str(settings.symbol)] = []
        for symbol, items in grouped_o.items():
            repo.record_exchange_snapshot(
                {
                    "reconcile_run_id": reconcile_run_id,
                    "symbol": symbol,
                    "snapshot_type": "orders",
                    "raw_data": {
                        "source": "rest_catchup",
                        "reason": reason,
                        "ingest_ts_ms": ingest_ts_ms,
                        "event_type": "order",
                        "channel": "orders",
                        "action": "snapshot",
                        "items": items,
                    },
                }
            )
            rows_orders += 1
    except Exception as exc:
        logger.warning("rest catchup orders_pending failed: %s", exc)
        raise

    try:
        presp = private.list_all_positions(priority=True)
        pitems = _positions_items_from_payload(presp.payload)
        grouped_p: dict[str, list[dict[str, Any]]] = {}
        for it in pitems:
            sym = str(it.get("instId") or it.get("symbol") or settings.symbol or "default")
            grouped_p.setdefault(sym, []).append(it)
        if not grouped_p:
            grouped_p[str(settings.symbol)] = []
        for symbol, items in grouped_p.items():
            repo.record_exchange_snapshot(
                {
                    "reconcile_run_id": reconcile_run_id,
                    "symbol": symbol,
                    "snapshot_type": "positions",
                    "raw_data": {
                        "source": "rest_catchup",
                        "reason": reason,
                        "ingest_ts_ms": ingest_ts_ms,
                        "event_type": "position",
                        "channel": "positions",
                        "action": "snapshot",
                        "items": items,
                    },
                }
            )
            rows_positions += 1
    except Exception as exc:
        logger.warning("rest catchup all_position failed: %s", exc)
        raise

    logger.info(
        "rest snapshot catchup ok reason=%s order_snapshot_rows=%s position_snapshot_rows=%s",
        reason,
        rows_orders,
        rows_positions,
    )
    return {
        "ok": True,
        "ingest_ts_ms": ingest_ts_ms,
        "order_snapshot_rows": rows_orders,
        "position_snapshot_rows": rows_positions,
        "reason": reason,
    }
