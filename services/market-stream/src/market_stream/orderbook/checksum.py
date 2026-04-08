from __future__ import annotations

import zlib

LevelPair = tuple[str, str]


def _crc32_signed(value: str) -> int:
    crc = zlib.crc32(value.encode("utf-8"))
    if crc & 0x80000000:
        crc = -((crc ^ 0xFFFFFFFF) + 1)
    return crc


def build_checksum_string(
    bids: list[LevelPair],
    asks: list[LevelPair],
    *,
    levels: int = 25,
) -> str:
    limited_bids = bids[:levels]
    limited_asks = asks[:levels]
    parts: list[str] = []
    index = 0
    while index < len(limited_bids) or index < len(limited_asks):
        if index < len(limited_bids):
            parts.append(f"{limited_bids[index][0]}:{limited_bids[index][1]}")
        if index < len(limited_asks):
            parts.append(f"{limited_asks[index][0]}:{limited_asks[index][1]}")
        index += 1
    return ":".join(parts)


def verify_checksum(
    bids: list[LevelPair],
    asks: list[LevelPair],
    *,
    expected: int,
    levels: int = 25,
) -> bool:
    return _crc32_signed(build_checksum_string(bids, asks, levels=levels)) == expected
