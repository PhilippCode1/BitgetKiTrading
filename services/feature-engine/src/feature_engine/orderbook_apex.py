"""Bridge zum nativen Apex-Orderbuch (`apex_core.ApexOrderBook` aus shared_rs).

Nutzt dieselbe Level-Semantik wie `market_stream.orderbook` (Listen von ``(preis, size)`` als float).
Falls `apex_core` nicht installiert ist, schlagen Hilfsfunktionen mit ``ImportError`` fehl.
"""

from __future__ import annotations

from typing import Any, Sequence

try:
    from apex_core import ApexOrderBook as _ApexOrderBook
    from apex_core import orderbook_crc32_signed as _orderbook_crc32_signed
except ImportError:  # pragma: no cover - optional native wheel
    _ApexOrderBook = None  # type: ignore[misc, assignment]
    _orderbook_crc32_signed = None  # type: ignore[misc, assignment]


def apex_orderbook_extension_available() -> bool:
    return _ApexOrderBook is not None


def orderbook_crc32_signed(checksum_utf8: str) -> int:
    """CRC32 wie Python `zlib.crc32` (signed int32) fuer rohe Checksum-Strings."""
    if _orderbook_crc32_signed is None:
        raise ImportError("apex_core nicht installiert (maturin develop im venv)")
    return int(_orderbook_crc32_signed(checksum_utf8))


def new_apex_orderbook(*, max_levels: int = 50, checksum_levels: int = 25) -> Any:
    if _ApexOrderBook is None:
        raise ImportError("apex_core nicht installiert (maturin develop im venv)")
    return _ApexOrderBook(max_levels, checksum_levels)


def levels_as_float_pairs(
    bids: Sequence[tuple[Any, Any]],
    asks: Sequence[tuple[Any, Any]],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Konvertiert Exchange-Levels (z. B. Decimal-Strings) zu float-Paaren fuer Rust."""
    bf = [(float(p), float(s)) for p, s in bids]
    af = [(float(p), float(s)) for p, s in asks]
    return bf, af


def apex_snapshot_dict_after_snapshot(
    bids: Sequence[tuple[Any, Any]],
    asks: Sequence[tuple[Any, Any]],
    *,
    seq: int | None = None,
    checksum: int | None = None,
    ingest_ts_ns: int | None = None,
    max_levels: int = 50,
    checksum_levels: int = 25,
) -> dict[str, Any]:
    """Einmaliges Snapshot-Anwenden und Rueckgabe von ``snapshot_dict()`` (DataFrame-tauglich)."""
    book = new_apex_orderbook(max_levels=max_levels, checksum_levels=checksum_levels)
    bl, al = levels_as_float_pairs(bids, asks)
    book.apply_snapshot_levels(bl, al, seq, checksum, ingest_ts_ns)
    return dict(book.snapshot_dict())
