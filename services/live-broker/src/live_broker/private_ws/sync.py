from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from live_broker.config import LiveBrokerSettings
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_ws.models import NormalizedPrivateEvent

logger = logging.getLogger("live_broker.private_ws.sync")
_DEFAULT_ORDER_SIZE = "0.00000001"


class ExchangeStateSyncService:
    def __init__(
        self,
        settings: LiveBrokerSettings,
        repo: LiveBrokerRepository,
    ) -> None:
        self._settings = settings
        self._repo = repo

    def handle_event(self, event: NormalizedPrivateEvent) -> dict[str, Any]:
        if event.event_type == "order":
            return self._handle_order_event(event)
        if event.event_type == "fill":
            return self._handle_fill_event(event)
        if event.event_type == "position":
            return self._handle_snapshot_event(event, snapshot_type="positions")
        if event.event_type == "account":
            return self._handle_snapshot_event(event, snapshot_type="account")
        return {"ok": True, "handled": False, "event_type": event.event_type}

    def restore_runtime_state(self) -> dict[str, Any]:
        return self._repo.reconstruct_runtime_state()

    def _handle_order_event(self, event: NormalizedPrivateEvent) -> dict[str, Any]:
        snapshots = self._persist_snapshot_groups(
            event,
            snapshot_type="orders",
            key_getter=lambda item: self._text(item.get("instId")) or event.inst_id,
        )
        orders = [self._upsert_order_from_ws_item(event, item) for item in event.data]
        return {
            "ok": True,
            "handled": True,
            "event_type": event.event_type,
            "snapshot_rows": len(snapshots),
            "orders_synced": len(orders),
        }

    def _handle_fill_event(self, event: NormalizedPrivateEvent) -> dict[str, Any]:
        fills = [self._record_fill_from_ws_item(event, item) for item in event.data]
        return {
            "ok": True,
            "handled": True,
            "event_type": event.event_type,
            "fills_recorded": len(fills),
        }

    def _handle_snapshot_event(
        self,
        event: NormalizedPrivateEvent,
        *,
        snapshot_type: str,
    ) -> dict[str, Any]:
        if snapshot_type == "positions":
            key_getter = lambda item: self._text(item.get("instId")) or event.inst_id
        else:
            key_getter = (
                lambda item: self._text(item.get("marginCoin"))
                or self._text(item.get("coin"))
                or event.inst_id
            )
        snapshots = self._persist_snapshot_groups(
            event,
            snapshot_type=snapshot_type,
            key_getter=key_getter,
        )
        return {
            "ok": True,
            "handled": True,
            "event_type": event.event_type,
            "snapshot_rows": len(snapshots),
        }

    def _persist_snapshot_groups(
        self,
        event: NormalizedPrivateEvent,
        *,
        snapshot_type: str,
        key_getter,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in event.data:
            grouped[str(key_getter(item) or event.inst_id or "default")].append(dict(item))
        if not grouped:
            grouped[str(event.inst_id or "default")] = []
        rows: list[dict[str, Any]] = []
        for symbol, items in grouped.items():
            rows.append(
                self._repo.record_exchange_snapshot(
                    {
                        "reconcile_run_id": None,
                        "symbol": symbol,
                        "snapshot_type": snapshot_type,
                        "raw_data": {
                            "event_type": event.event_type,
                            "channel": event.channel,
                            "action": event.action,
                            "inst_type": event.inst_type,
                            "inst_id": event.inst_id,
                            "arg": event.arg_json,
                            "exchange_ts_ms": event.exchange_ts_ms,
                            "ingest_ts_ms": event.ingest_ts_ms,
                            "items": items,
                        },
                    }
                )
            )
        return rows

    def _upsert_order_from_ws_item(
        self,
        event: NormalizedPrivateEvent,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._find_existing_order(item)
        internal_order_id = self._order_internal_id(item, existing)
        product_type = self._text(item.get("productType")) or event.inst_type or self._settings.product_type
        margin_coin = self._text(item.get("marginCoin")) or self._settings.effective_margin_coin
        client_oid = self._text(item.get("clientOid"))
        exchange_order_id = self._text(item.get("orderId"))
        status = self._text(item.get("status")) or (existing or {}).get("status") or "ws_synced"
        trace_json = {
            **((existing or {}).get("trace_json") or {}),
            "ws_channel": event.channel,
            "ws_action": event.action,
            "ws_exchange_ts_ms": event.exchange_ts_ms,
        }
        return self._repo.upsert_order(
            {
                "internal_order_id": internal_order_id,
                "parent_internal_order_id": (existing or {}).get("parent_internal_order_id"),
                "source_service": (existing or {}).get("source_service") or "exchange-sync",
                "symbol": self._text(item.get("instId")) or event.inst_id or self._settings.symbol,
                "product_type": product_type,
                "margin_mode": self._text(item.get("marginMode")) or (existing or {}).get("margin_mode") or "isolated",
                "margin_coin": margin_coin,
                "side": self._text(item.get("side")) or (existing or {}).get("side") or "buy",
                "trade_side": self._text(item.get("tradeSide")) or (existing or {}).get("trade_side"),
                "order_type": self._text(item.get("orderType")) or (existing or {}).get("order_type") or "limit",
                "force": self._text(item.get("force")) or (existing or {}).get("force"),
                "reduce_only": self._bool_yes_no(item.get("reduceOnly"), default=bool((existing or {}).get("reduce_only"))),
                "size": self._text(item.get("size"))
                or self._text(item.get("accBaseVolume"))
                or self._text(item.get("baseVolume"))
                or (existing or {}).get("size")
                or _DEFAULT_ORDER_SIZE,
                "price": self._text(item.get("price"))
                or self._text(item.get("priceAvg"))
                or self._text(item.get("fillPrice"))
                or (existing or {}).get("price"),
                "note": (existing or {}).get("note") or "",
                "client_oid": client_oid or (existing or {}).get("client_oid") or self._stable_order_seed(item),
                "exchange_order_id": exchange_order_id or (existing or {}).get("exchange_order_id"),
                "status": status,
                "last_action": "ws_sync",
                "last_http_status": (existing or {}).get("last_http_status"),
                "last_exchange_code": (existing or {}).get("last_exchange_code"),
                "last_exchange_msg": f"ws:{event.channel}:{event.action}",
                "last_response_json": item,
                "trace_json": trace_json,
            }
        )

    def _record_fill_from_ws_item(
        self,
        event: NormalizedPrivateEvent,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._find_existing_order(item)
        internal_order_id = self._order_internal_id(item, existing)
        client_oid = self._text(item.get("clientOid"))
        exchange_order_id = self._text(item.get("orderId"))
        if existing is None:
            self._repo.upsert_order(
                {
                    "internal_order_id": internal_order_id,
                    "parent_internal_order_id": None,
                    "source_service": "exchange-sync",
                    "symbol": self._text(item.get("symbol")) or event.inst_id or self._settings.symbol,
                    "product_type": event.inst_type or self._settings.product_type,
                    "margin_mode": "isolated",
                    "margin_coin": self._first_fee_coin(item) or self._settings.effective_margin_coin,
                    "side": self._text(item.get("side")) or "buy",
                    "trade_side": self._text(item.get("tradeSide")),
                    "order_type": self._text(item.get("orderType")) or "market",
                    "force": None,
                    "reduce_only": self._is_reduce_trade_side(item.get("tradeSide")),
                    "size": self._text(item.get("baseVolume")) or _DEFAULT_ORDER_SIZE,
                    "price": self._text(item.get("price")),
                    "note": "recovered_from_fill",
                    "client_oid": client_oid or self._stable_order_seed(item),
                    "exchange_order_id": exchange_order_id,
                    "status": "filled",
                    "last_action": "ws_fill_sync",
                    "last_http_status": None,
                    "last_exchange_code": None,
                    "last_exchange_msg": "ws:fill",
                    "last_response_json": item,
                    "trace_json": {
                        "ws_channel": event.channel,
                        "ws_action": event.action,
                        "ws_exchange_ts_ms": event.exchange_ts_ms,
                    },
                }
            )
        return self._repo.record_fill(
            {
                "internal_order_id": internal_order_id,
                "exchange_order_id": exchange_order_id,
                "exchange_trade_id": self._text(item.get("tradeId")) or self._stable_fill_seed(item),
                "symbol": self._text(item.get("symbol")) or event.inst_id or self._settings.symbol,
                "side": self._text(item.get("side")) or "buy",
                "price": self._text(item.get("price")) or "0",
                "size": self._text(item.get("baseVolume")) or "0",
                "fee": self._first_fee_amount(item),
                "fee_coin": self._first_fee_coin(item) or self._settings.effective_margin_coin,
                "is_maker": self._is_maker_fill(item),
                "exchange_ts_ms": self._text(item.get("uTime"))
                or self._text(item.get("cTime"))
                or str(event.exchange_ts_ms),
                "ingest_source": "private_ws",
                "raw_json": item,
            }
        )

    def _find_existing_order(self, item: dict[str, Any]) -> dict[str, Any] | None:
        client_oid = self._text(item.get("clientOid"))
        if client_oid:
            existing = self._repo.get_order_by_client_oid(client_oid)
            if existing is not None:
                return existing
        exchange_order_id = self._text(item.get("orderId"))
        if exchange_order_id:
            existing = self._repo.get_order_by_exchange_order_id(exchange_order_id)
            if existing is not None:
                return existing
        return None

    def _order_internal_id(
        self,
        item: dict[str, Any],
        existing: dict[str, Any] | None,
    ) -> str:
        if existing is not None:
            return str(existing["internal_order_id"])
        return str(
            uuid5(
                NAMESPACE_URL,
                f"bitget-order:{self._stable_order_seed(item)}",
            )
        )

    def _stable_order_seed(self, item: dict[str, Any]) -> str:
        client_oid = self._text(item.get("clientOid"))
        if client_oid:
            return client_oid
        exchange_order_id = self._text(item.get("orderId"))
        if exchange_order_id:
            return exchange_order_id
        return json.dumps(item, sort_keys=True, separators=(",", ":"))

    def _stable_fill_seed(self, item: dict[str, Any]) -> str:
        payload = json.dumps(item, sort_keys=True, separators=(",", ":"))
        return str(uuid5(NAMESPACE_URL, f"bitget-fill:{payload}"))

    def _first_fee_amount(self, item: dict[str, Any]) -> str:
        fee_detail = item.get("feeDetail")
        if isinstance(fee_detail, list):
            for entry in fee_detail:
                if not isinstance(entry, dict):
                    continue
                value = self._text(entry.get("totalFee")) or self._text(entry.get("fee"))
                if value is not None:
                    return value
        return self._text(item.get("fillFee")) or self._text(item.get("fee")) or "0"

    def _first_fee_coin(self, item: dict[str, Any]) -> str | None:
        fee_detail = item.get("feeDetail")
        if isinstance(fee_detail, list):
            for entry in fee_detail:
                if not isinstance(entry, dict):
                    continue
                value = self._text(entry.get("feeCoin"))
                if value is not None:
                    return value
        return self._text(item.get("fillFeeCoin"))

    def _is_maker_fill(self, item: dict[str, Any]) -> bool:
        value = (self._text(item.get("tradeScope")) or "").lower()
        return value in {"maker", "m"}

    def _is_reduce_trade_side(self, value: object) -> bool:
        normalized = (self._text(value) or "").lower()
        return "close" in normalized or normalized.startswith("reduce_")

    def _bool_yes_no(self, value: object, *, default: bool = False) -> bool:
        normalized = (self._text(value) or "").lower()
        if not normalized:
            return default
        return normalized in {"yes", "true", "1"}

    def _text(self, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
