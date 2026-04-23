from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from shared_py.bitget import BitgetSettings

from market_stream.bitget_ws.subscriptions import Subscription
from market_stream.storage.trades_repo import TradesRepository


@dataclass(frozen=True)
class TradeRecord:
    symbol: str
    trade_id: str
    ts_ms: int
    price: Decimal
    size: Decimal
    side: str
    ingest_ts_ms: int


class TradesCollector:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        trades_repo: TradesRepository,
        on_trades_batch: Callable[[list[TradeRecord]], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._trades_repo = trades_repo
        self._on_trades_batch = on_trades_batch
        self._logger = logger or logging.getLogger("market_stream.trades")
        self._last_trade_ts_ms: int | None = None
        self._last_trade_id: str | None = None
        self._persisted_trades = 0

    def subscriptions(self) -> list[Subscription]:
        return [
            Subscription(
                inst_type=self._bitget_settings.public_ws_inst_type,
                channel="trade",
                inst_id=self._bitget_settings.symbol,
            )
        ]

    def last_trade_ts_ms(self) -> int | None:
        return self._last_trade_ts_ms

    def stats_payload(self) -> dict[str, object]:
        return {
            "last_trade_ts_ms": self._last_trade_ts_ms,
            "last_trade_id": self._last_trade_id,
            "persisted_trades": self._persisted_trades,
        }

    async def start(self) -> None:
        await self._trades_repo.connect()

    async def stop(self) -> None:
        await self._trades_repo.close()

    async def handle_ws_message(self, message: dict[str, Any]) -> None:
        arg = message.get("arg")
        if not isinstance(arg, dict) or arg.get("channel") != "trade":
            return
        data = message.get("data")
        if not isinstance(data, list):
            return

        trades: list[TradeRecord] = []
        for item in data:
            try:
                trade = parse_trade_record(self._bitget_settings.symbol, item)
            except (InvalidOperation, ValueError) as exc:
                self._logger.warning("failed to parse trade payload error=%s item=%s", exc, item)
                continue
            trades.append(trade)
        if trades and self._on_trades_batch is not None:
            try:
                self._on_trades_batch(trades)
            except Exception as exc:
                self._logger.debug("on_trades_batch hook failed: %s", exc)
        inserted = await self._trades_repo.upsert_trades(trades)
        self._persisted_trades += inserted
        if trades:
            last_trade = trades[-1]
            self._last_trade_ts_ms = last_trade.ts_ms
            self._last_trade_id = last_trade.trade_id


def parse_trade_record(symbol: str, item: Any) -> TradeRecord:
    if isinstance(item, dict):
        trade_id = _require_str(item, "tradeId", "id")
        ts_ms = _require_int(item, "ts", "timestamp")
        price = _require_decimal(item, "price")
        size = _require_decimal(item, "size")
        side = _normalize_side(_require_str(item, "side"))
        return TradeRecord(
            symbol=symbol,
            trade_id=trade_id,
            ts_ms=ts_ms,
            price=price,
            size=size,
            side=side,
            ingest_ts_ms=int(time.time() * 1000),
        )

    if isinstance(item, list) and len(item) >= 5:
        if str(item[0]).isdigit():
            ts_ms = int(str(item[0]))
            price = Decimal(str(item[1]))
            size = Decimal(str(item[2]))
            side = _normalize_side(str(item[3]))
            trade_id = str(item[4])
        else:
            trade_id = str(item[0])
            price = Decimal(str(item[1]))
            size = Decimal(str(item[2]))
            side = _normalize_side(str(item[3]))
            ts_ms = int(str(item[4]))
        return TradeRecord(
            symbol=symbol,
            trade_id=trade_id,
            ts_ms=ts_ms,
            price=price,
            size=size,
            side=side,
            ingest_ts_ms=int(time.time() * 1000),
        )

    raise ValueError(f"unsupported trade payload: {item}")


def _require_str(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, bool):
            normalized = str(value).strip()
            if normalized:
                return normalized
    raise ValueError(f"missing string keys {keys}")


def _require_int(item: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            return int(value.strip())
    raise ValueError(f"missing int keys {keys}")


def _require_decimal(item: dict[str, Any], *keys: str) -> Decimal:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        return Decimal(str(value))
    raise ValueError(f"missing decimal keys {keys}")


def _normalize_side(value: str) -> str:
    side = value.strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError(f"unsupported trade side: {value}")
    return side
