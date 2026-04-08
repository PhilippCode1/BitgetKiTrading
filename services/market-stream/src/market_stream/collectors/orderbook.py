from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from shared_py.bitget import BitgetSettings

from market_stream.bitget_ws.subscriptions import Subscription
from market_stream.metrics.slippage import compute_slippage_metrics
from market_stream.normalization.models import (
    NormalizedEvent,
    extract_exchange_ts_ms,
    extract_sequence,
)
from market_stream.orderbook.book import (
    LocalOrderBook,
    OrderBookChecksumError,
    OrderBookSequenceError,
)
from market_stream.sinks.redis_stream import RedisStreamSink
from market_stream.storage.orderbook_repo import OrderBookRepository

LevelPair = tuple[str, str]
ResyncAction = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class OrderBookPersistSnapshot:
    symbol: str
    ts_ms: int
    seq: int | None
    checksum: int | None
    bids: list[LevelPair]
    asks: list[LevelPair]


class OrderbookCollector:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        orderbook_repo: OrderBookRepository,
        slippage_sink: RedisStreamSink,
        max_levels: int,
        checksum_levels: int,
        resync_on_mismatch: bool,
        slippage_sizes_usdt: list[int],
        logger: logging.Logger | None = None,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._orderbook_repo = orderbook_repo
        self._slippage_sink = slippage_sink
        self._logger = logger or logging.getLogger("market_stream.orderbook")
        self._book = LocalOrderBook(
            max_levels=max_levels,
            checksum_levels=checksum_levels,
        )
        self._max_levels = max_levels
        self._checksum_levels = checksum_levels
        self._resync_on_mismatch = resync_on_mismatch
        self._slippage_sizes_usdt = slippage_sizes_usdt
        self._resync_action: ResyncAction | None = None
        self._awaiting_books5_recovery = False
        self._last_orderbook_ts_ms: int | None = None
        self._last_slippage_ts_ms: int | None = None
        self._checksum_mismatch_count = 0
        self._resync_count = 0
        self._last_resync_reason: str | None = None
        self._last_resync_trigger_ts_ms: int | None = None
        self._last_seq: int | None = None
        self._persisted_snapshots = 0
        self._published_slippage_events = 0
        self._resync_cooldown_ms = 5_000

    def bind_resync_action(self, action: ResyncAction) -> None:
        self._resync_action = action

    def subscriptions(self) -> list[Subscription]:
        return [
            Subscription(
                inst_type=self._bitget_settings.public_ws_inst_type,
                channel="books",
                inst_id=self._bitget_settings.symbol,
            ),
            Subscription(
                inst_type=self._bitget_settings.public_ws_inst_type,
                channel="books5",
                inst_id=self._bitget_settings.symbol,
            ),
        ]

    def last_orderbook_ts_ms(self) -> int | None:
        return self._last_orderbook_ts_ms

    def stats_payload(self) -> dict[str, object]:
        return {
            "orderbook_last_ts_ms": self._last_orderbook_ts_ms,
            "orderbook_last_seq": self._last_seq,
            "orderbook_desynced": self._book.desynced,
            "orderbook_desync_reason": self._book.desync_reason,
            "orderbook_checksum_mismatch_count": self._checksum_mismatch_count,
            "orderbook_resync_count": self._resync_count,
            "orderbook_last_resync_reason": self._last_resync_reason,
            "orderbook_persisted_snapshots": self._persisted_snapshots,
            "slippage_last_ts_ms": self._last_slippage_ts_ms,
            "slippage_published_events": self._published_slippage_events,
        }

    async def start(self) -> None:
        await self._orderbook_repo.connect()
        await self._slippage_sink.connect()

    async def stop(self) -> None:
        await self._orderbook_repo.close()
        await self._slippage_sink.close()

    async def on_connected(self, *, is_reconnect: bool) -> None:
        if is_reconnect:
            self._book.reset()
            self._awaiting_books5_recovery = False

    async def handle_ws_message(self, message: dict[str, Any]) -> None:
        arg = message.get("arg")
        if not isinstance(arg, dict):
            return
        channel = arg.get("channel")
        if channel not in {"books", "books5"}:
            return
        data = message.get("data")
        if not isinstance(data, list) or not data:
            return

        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                await self._handle_orderbook_item(
                    message=message,
                    item=item,
                    channel=channel,
                )
            except ValueError as exc:
                self._logger.warning("failed to parse orderbook payload error=%s item=%s", exc, item)

    async def _handle_orderbook_item(
        self,
        *,
        message: dict[str, Any],
        item: dict[str, Any],
        channel: str,
    ) -> None:
        bids = _extract_levels(item.get("bids"))
        asks = _extract_levels(item.get("asks"))
        seq = _extract_sequence(message, item)
        checksum = _extract_checksum(message, item)
        ts_ms = _extract_ts_ms(message, item)
        action = str(message.get("action") or "update").lower()

        if channel == "books5":
            if not self._awaiting_books5_recovery and self._book.seq is not None and not self._book.desynced:
                return
            try:
                view = self._book.apply_snapshot(
                    bids=bids,
                    asks=asks,
                    seq=seq,
                    checksum=checksum,
                    ts_ms=ts_ms,
                )
            except OrderBookChecksumError as exc:
                self._checksum_mismatch_count += 1
                await self._trigger_resync(reason=f"books5-{exc}")
                return
            await self._persist_and_publish(
                OrderBookPersistSnapshot(
                    symbol=self._bitget_settings.symbol,
                    ts_ms=ts_ms,
                    seq=view.seq,
                    checksum=view.checksum,
                    bids=view.bids,
                    asks=view.asks,
                ),
                source_channel=channel,
            )
            self._awaiting_books5_recovery = False
            self._last_orderbook_ts_ms = ts_ms
            self._last_seq = view.seq
            return

        use_snapshot = action == "snapshot" or self._book.seq is None or self._book.desynced
        try:
            if use_snapshot:
                view = self._book.apply_snapshot(
                    bids=bids,
                    asks=asks,
                    seq=seq,
                    checksum=checksum,
                    ts_ms=ts_ms,
                )
            else:
                view = self._book.apply_update(
                    bids=bids,
                    asks=asks,
                    seq=seq,
                    checksum=checksum,
                    ts_ms=ts_ms,
                )
        except OrderBookChecksumError as exc:
            self._checksum_mismatch_count += 1
            self._logger.warning(
                "orderbook_checksum_mismatch symbol=%s expected=%s actual=%s reason=%s",
                self._bitget_settings.symbol,
                checksum,
                self._book.current_checksum(),
                exc,
            )
            await self._trigger_resync(reason=f"checksum-mismatch-{checksum}")
            return
        except OrderBookSequenceError as exc:
            self._logger.warning(
                "orderbook_seq_desync symbol=%s previous=%s current=%s reason=%s",
                self._bitget_settings.symbol,
                self._last_seq,
                seq,
                exc,
            )
            await self._trigger_resync(reason=str(exc))
            return

        self._last_orderbook_ts_ms = ts_ms
        self._last_seq = view.seq
        await self._persist_and_publish(
            OrderBookPersistSnapshot(
                symbol=self._bitget_settings.symbol,
                ts_ms=ts_ms,
                seq=view.seq,
                checksum=view.checksum,
                bids=view.bids,
                asks=view.asks,
            ),
            source_channel=channel,
        )

    async def _persist_and_publish(
        self,
        snapshot: OrderBookPersistSnapshot,
        *,
        source_channel: str,
    ) -> None:
        inserted = await self._orderbook_repo.insert_snapshot(snapshot)
        if inserted:
            self._persisted_snapshots += 1

        try:
            slippage_payload = compute_slippage_metrics(
                symbol=snapshot.symbol,
                ts_ms=snapshot.ts_ms,
                bids=snapshot.bids,
                asks=snapshot.asks,
                sizes_usdt=self._slippage_sizes_usdt,
                top_n=self._max_levels,
            )
        except ValueError:
            return

        event = NormalizedEvent(
            source="bitget_orderbook_metrics",
            inst_type=self._bitget_settings.public_ws_inst_type,
            channel="slippage_metrics",
            inst_id=self._bitget_settings.symbol,
            action="snapshot",
            exchange_ts_ms=snapshot.ts_ms,
            payload={
                **slippage_payload,
                "seq": snapshot.seq,
                "checksum": snapshot.checksum,
                "source_channel": source_channel,
            },
        )
        redis_id = await self._slippage_sink.publish(event)
        if redis_id is not None:
            self._published_slippage_events += 1
            self._last_slippage_ts_ms = snapshot.ts_ms

    async def _trigger_resync(self, *, reason: str) -> None:
        self._last_resync_reason = reason
        now_ms = int(time.time() * 1000)
        if (
            self._last_resync_trigger_ts_ms is not None
            and now_ms - self._last_resync_trigger_ts_ms < self._resync_cooldown_ms
        ):
            return
        self._last_resync_trigger_ts_ms = now_ms
        self._resync_count += 1
        self._awaiting_books5_recovery = True
        self._book.mark_desynced(reason)
        self._logger.warning("orderbook resync triggered reason=%s", reason)
        if self._resync_on_mismatch and self._resync_action is not None:
            await self._resync_action(reason)


def _extract_levels(raw_levels: object) -> list[LevelPair]:
    if not isinstance(raw_levels, list):
        raise ValueError("orderbook side muss eine Liste sein")
    levels: list[LevelPair] = []
    for item in raw_levels:
        if isinstance(item, list) and len(item) >= 2:
            levels.append((str(item[0]), str(item[1])))
            continue
        if isinstance(item, dict):
            price = item.get("price")
            size = item.get("size")
            if price is None or size is None:
                raise ValueError(f"ungueltiges level object: {item}")
            levels.append((str(price), str(size)))
            continue
        raise ValueError(f"ungueltiges level payload: {item}")
    return levels


def _extract_sequence(message: dict[str, Any], item: dict[str, Any]) -> int | None:
    item_seq = item.get("seq")
    if item_seq is not None:
        return int(str(item_seq))
    return extract_sequence(message)


def _extract_checksum(message: dict[str, Any], item: dict[str, Any]) -> int | None:
    value = item.get("checksum", message.get("checksum"))
    if value is None or value == "":
        return None
    parsed = int(str(value))
    return None if parsed == 0 else parsed


def _extract_ts_ms(message: dict[str, Any], item: dict[str, Any]) -> int:
    item_ts = item.get("ts")
    if item_ts is not None and item_ts != "":
        return int(str(item_ts))
    return extract_exchange_ts_ms(message) or int(time.time() * 1000)
