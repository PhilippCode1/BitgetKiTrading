from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from market_stream.orderbook.checksum import _crc32_signed, build_checksum_string

LevelPair = tuple[str, str]


class OrderBookError(Exception):
    pass


class OrderBookSequenceError(OrderBookError):
    pass


class OrderBookChecksumError(OrderBookError):
    pass


@dataclass(frozen=True)
class OrderBookView:
    bids: list[LevelPair]
    asks: list[LevelPair]
    seq: int | None
    checksum: int | None
    ts_ms: int | None
    desynced: bool


class LocalOrderBook:
    def __init__(
        self,
        *,
        max_levels: int = 50,
        checksum_levels: int = 25,
        require_contiguous_seq: bool = False,
    ) -> None:
        if max_levels < 1:
            raise ValueError("max_levels muss >= 1 sein")
        if checksum_levels < 1:
            raise ValueError("checksum_levels muss >= 1 sein")
        if max_levels < checksum_levels:
            raise ValueError("max_levels muss >= checksum_levels sein")
        self._max_levels = max_levels
        self._checksum_levels = checksum_levels
        self._require_contiguous_seq = require_contiguous_seq
        self._bids: dict[str, str] = {}
        self._asks: dict[str, str] = {}
        self._seq: int | None = None
        self._checksum: int | None = None
        self._ts_ms: int | None = None
        self._desynced = False
        self._desync_reason: str | None = None

    @property
    def seq(self) -> int | None:
        return self._seq

    @property
    def checksum(self) -> int | None:
        return self._checksum

    @property
    def ts_ms(self) -> int | None:
        return self._ts_ms

    @property
    def desynced(self) -> bool:
        return self._desynced

    @property
    def desync_reason(self) -> str | None:
        return self._desync_reason

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._seq = None
        self._checksum = None
        self._ts_ms = None
        self._desynced = False
        self._desync_reason = None

    def mark_desynced(self, reason: str) -> None:
        self._desynced = True
        self._desync_reason = reason

    def apply_snapshot(
        self,
        *,
        bids: list[LevelPair],
        asks: list[LevelPair],
        seq: int | None,
        checksum: int | None,
        ts_ms: int | None,
    ) -> OrderBookView:
        self._bids = self._build_side_map(bids, descending=True)
        self._asks = self._build_side_map(asks, descending=False)
        self._seq = seq
        self._checksum = checksum
        self._ts_ms = ts_ms
        self._desynced = False
        self._desync_reason = None
        self._validate_checksum()
        return self.view()

    def apply_update(
        self,
        *,
        bids: list[LevelPair],
        asks: list[LevelPair],
        seq: int | None,
        checksum: int | None,
        ts_ms: int | None,
    ) -> OrderBookView:
        if self._desynced:
            raise OrderBookSequenceError(
                f"orderbook ist desynchronisiert: {self._desync_reason or 'unknown'}"
            )
        if seq is not None and self._seq is not None:
            if seq <= self._seq:
                self.mark_desynced(f"seq-regression-{self._seq}-{seq}")
                raise OrderBookSequenceError(
                    f"seq regression previous={self._seq} current={seq}"
                )
            if self._require_contiguous_seq and seq > self._seq + 1:
                self.mark_desynced(f"seq-gap-{self._seq}-{seq}")
                raise OrderBookSequenceError(f"seq gap previous={self._seq} current={seq}")

        self._merge_levels(self._bids, bids, descending=True)
        self._merge_levels(self._asks, asks, descending=False)
        if seq is not None:
            self._seq = seq
        self._checksum = checksum
        if ts_ms is not None:
            self._ts_ms = ts_ms
        self._validate_checksum()
        return self.view()

    def top_bids(self, levels: int | None = None) -> list[LevelPair]:
        limit = self._max_levels if levels is None else levels
        return self._sorted_levels(self._bids, descending=True)[:limit]

    def top_asks(self, levels: int | None = None) -> list[LevelPair]:
        limit = self._max_levels if levels is None else levels
        return self._sorted_levels(self._asks, descending=False)[:limit]

    def current_checksum(self) -> int:
        value = build_checksum_string(
            self.top_bids(self._checksum_levels),
            self.top_asks(self._checksum_levels),
            levels=self._checksum_levels,
        )
        return _crc32_signed(value)

    def view(self) -> OrderBookView:
        return OrderBookView(
            bids=self.top_bids(),
            asks=self.top_asks(),
            seq=self._seq,
            checksum=self._checksum,
            ts_ms=self._ts_ms,
            desynced=self._desynced,
        )

    def _validate_checksum(self) -> None:
        if self._checksum is None:
            return
        actual_checksum = self.current_checksum()
        if actual_checksum != self._checksum:
            self.mark_desynced(
                f"checksum-mismatch-expected-{self._checksum}-actual-{actual_checksum}"
            )
            raise OrderBookChecksumError(
                f"checksum mismatch expected={self._checksum} actual={actual_checksum}"
            )

    def _build_side_map(
        self,
        levels: list[LevelPair],
        *,
        descending: bool,
    ) -> dict[str, str]:
        side: dict[str, str] = {}
        for price, size in levels:
            self._validate_numeric_pair(price, size)
            if _is_zero(size):
                continue
            side[price] = size
        ordered = self._sorted_levels(side, descending=descending)[: self._max_levels]
        return {price: size for price, size in ordered}

    def _merge_levels(
        self,
        side: dict[str, str],
        levels: list[LevelPair],
        *,
        descending: bool,
    ) -> None:
        for price, size in levels:
            self._validate_numeric_pair(price, size)
            if _is_zero(size):
                side.pop(price, None)
            else:
                side[price] = size
        ordered = self._sorted_levels(side, descending=descending)[: self._max_levels]
        side.clear()
        side.update(ordered)

    def _sorted_levels(
        self,
        side: dict[str, str],
        *,
        descending: bool,
    ) -> list[LevelPair]:
        return sorted(
            side.items(),
            key=lambda item: Decimal(item[0]),
            reverse=descending,
        )

    @staticmethod
    def _validate_numeric_pair(price: str, size: str) -> None:
        try:
            Decimal(price)
            Decimal(size)
        except InvalidOperation as exc:
            raise ValueError(f"ungueltiges price/size pair: {price}/{size}") from exc


def _is_zero(value: str) -> bool:
    return Decimal(value) == 0
