from __future__ import annotations

import zlib

# Bitget books/books5-Checksum, vgl. shared_rs/orderbook: indexweise abwechselnd bid/ask
# je Stufe: Preis, Size, Join mit «:», CRC32 wie zlib (32-bit signed).

LevelPair = tuple[str, str]

_SIGNED_MASK = 0xFFFFFFFF
_SIGN_BIT = 0x80000000


def crc32_bitget_signed(utf8_payload: str) -> int:
    """Vollstaendig gebauter Checksum-String (nicht: einzelprices) -> signed CRC32."""
    crc = zlib.crc32(utf8_payload.encode("utf-8")) & _SIGNED_MASK
    if crc & _SIGN_BIT:
        return -int((crc ^ _SIGNED_MASK) + 1)
    return int(crc)


def build_checksum_string(
    bids: list[LevelPair],
    asks: list[LevelPair],
    *,
    levels: int = 25,
) -> str:
    """
    Exakter Bitget-Buffer fuer CRC: je Index i: bid-Preis, bid-Size, ask-Preis, ask-Size
    (fehlende Seite wird fuer diesen Index weggelassen, analog Rust).
    """
    if levels < 1:
        return ""
    lb = bids[:levels]
    la = asks[:levels]
    parts: list[str] = []
    i = 0
    while i < len(lb) or i < len(la):
        if i < len(lb):
            parts.append(lb[i][0])
            parts.append(lb[i][1])
        if i < len(la):
            parts.append(la[i][0])
            parts.append(la[i][1])
        i += 1
    return ":".join(parts)


def _crc32_signed(value: str) -> int:
    """Low-Level: CRC eines bereits formattierten Strings (Tests / LocalOrderBook)."""
    return crc32_bitget_signed(value)


def compute_bitget_orderbook_crc32(
    bids: list[LevelPair],
    asks: list[LevelPair],
    *,
    levels: int = 25,
) -> int:
    return _crc32_signed(build_checksum_string(bids, asks, levels=levels))


def verify_checksum(
    bids: list[LevelPair],
    asks: list[LevelPair],
    *,
    expected: int,
    levels: int = 25,
) -> bool:
    return compute_bitget_orderbook_crc32(bids, asks, levels=levels) == int(expected)
