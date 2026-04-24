"""
Pre-Execution Liquiditaets-Check: Top-5-Orderbook (Redis-Snapshot vom market-stream),
erwarteter Slippage in bps vs. Mid — Block oberhalb Schwelle.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from shared_py.redis_client import create_sync_connection_pool, sync_redis_from_pool

logger = logging.getLogger("live_broker.execution.liquidity_guard")

# Redis-Key, den market-stream bei jedem gueltigen Book-Update setzt
ORDERBOOK_TOP5_REDIS_PREFIX = "ms:orderbook_top5:"

# 50 bps = 0,5 % Kursverschiebung vs. Mid (Prompt 30)
_DEFAULT_MAX_SLIPPAGE_BPS = Decimal("50")
_TOPN_USE = 5

_BLOCKED_LOG = "Blocked by Liquidity Guard"


class InsufficientLiquidityError(Exception):
    """
    Taker-Order wuerde Slippage > Schwelle erzeugen oder Top-5-Depth reicht nicht.
    """

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


# Historische/externe Bezeichnung (Prompt 30)
InsufficientLiquidityException = InsufficientLiquidityError


def _dec(x: Any) -> Decimal:
    if x in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_levels(
    raw_bids: Any,
    raw_asks: Any,
) -> tuple[list[tuple[Decimal, Decimal]], list[tuple[Decimal, Decimal]]]:
    def _one_side(data: Any, *, reverse: bool) -> list[tuple[Decimal, Decimal]]:
        if not isinstance(data, list):
            return []
        out: list[tuple[Decimal, Decimal]] = []
        for item in data[:_TOPN_USE]:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            p, s = _dec(item[0]), _dec(item[1])
            if p > 0 and s > 0:
                out.append((p, s))
        if reverse:
            out.sort(key=lambda t: t[0], reverse=True)
        return out

    # Bids: bestes (hoechstes) zuerst; Asks: bestes (niedrigstes) zuerst
    return _one_side(raw_bids, reverse=True), _one_side(raw_asks, reverse=False)


def _mid_price(bids: list[tuple[Decimal, Decimal]], asks: list[tuple[Decimal, Decimal]]) -> Decimal:
    if not bids or not asks:
        return Decimal("0")
    return (bids[0][0] + asks[0][0]) / Decimal("2")


def _vwap_buy(asks: list[tuple[Decimal, Decimal]], size: Decimal) -> tuple[Decimal | None, str | None]:
    rem = size
    cost = Decimal("0")
    for p, s in asks:
        if rem <= 0:
            break
        use = rem if s >= rem else s
        cost += use * p
        rem -= use
    if rem > Decimal("0"):
        return None, "insufficient_top5_depth"
    return cost / size, None


def _vwap_sell(
    bids: list[tuple[Decimal, Decimal]], size: Decimal
) -> tuple[Decimal | None, str | None]:
    rem = size
    quote = Decimal("0")
    for p, s in bids:
        if rem <= 0:
            break
        use = rem if s >= rem else s
        quote += use * p
        rem -= use
    if rem > Decimal("0"):
        return None, "insufficient_top5_depth"
    return quote / size, None


def _slippage_bps_vs_mid(
    *,
    mid: Decimal,
    vwap: Decimal,
    side: str,
) -> Decimal:
    if mid <= 0 or vwap <= 0:
        return Decimal("99999")
    s = side.strip().lower()
    if s == "buy":
        diff = vwap - mid
    elif s == "sell":
        diff = mid - vwap
    else:
        return Decimal("99999")
    if diff < 0:
        diff = -diff
    return (diff / mid) * Decimal("10000")


def _load_snapshot_from_redis(redis_url: str, symbol: str) -> dict[str, Any] | None:
    if not (redis_url or "").strip():
        return None
    key = f"{ORDERBOOK_TOP5_REDIS_PREFIX}{symbol}"
    pool = create_sync_connection_pool(
        redis_url,
        decode_responses=True,
        max_connections=2,
        socket_connect_timeout=1.5,
        socket_timeout=1.5,
    )
    r = sync_redis_from_pool(pool, health_check_interval=30)
    try:
        raw = r.get(key)
    finally:
        try:
            r.close()
        except Exception:  # pragma: no cover
            pass
        try:
            pool.disconnect()
        except Exception:  # pragma: no cover
            pass
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else None
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def verify_execution_liquidity(
    symbol: str,
    size: Decimal,
    side: str,
    redis_url: str = "",
    *,
    max_slippage_bps: Decimal | None = None,
    strict: bool = True,
    _snapshot: dict[str, Any] | None = None,
) -> None:
    """
    Liest Top-5 aus Redis-JSON (ms:orderbook_top5:{symbol}) und prueft erwartete Slippage
    (VWAP vs. Mid). Bei Ueber-/Unterdeckung: :class:`InsufficientLiquidityError`.
    """
    if size <= 0:
        return
    cap = _DEFAULT_MAX_SLIPPAGE_BPS if max_slippage_bps is None else max_slippage_bps
    if cap <= 0:
        return

    snap: dict[str, Any] | None
    if _snapshot is not None:
        snap = _snapshot
    else:
        snap = _load_snapshot_from_redis(redis_url, symbol) if redis_url else None
    if snap is None:
        if not strict:
            logger.warning(
                "Liquidity guard: no Redis top5 (symbol=%s) — not strict, submit allowed",
                symbol,
            )
            return
        msg = f"{_BLOCKED_LOG}: kein orderbook top5 in Redis (symbol={symbol!s})"
        raise InsufficientLiquidityError(
            msg,
            detail={"symbol": symbol, "side": side, "reason": "orderbook_cache_missing"},
        )
    raw_b = snap.get("bids")
    raw_a = snap.get("asks")
    bids, asks = _parse_levels(raw_b, raw_a)
    if not bids or not asks:
        msg = f"{_BLOCKED_LOG}: leeres Bid/Ask (symbol={symbol!s})"
        raise InsufficientLiquidityError(
            msg,
            detail={"symbol": symbol, "side": side, "reason": "book_empty"},
        )
    side_l = (side or "").strip().lower()
    mid = _mid_price(bids, asks)
    if mid <= 0:
        msg = f"{_BLOCKED_LOG}: ungueltiger mid (symbol={symbol!s})"
        raise InsufficientLiquidityError(
            msg,
            detail={"symbol": symbol, "side": side, "reason": "no_mid"},
        )
    vwap: Decimal | None
    vwhy: str | None
    if side_l == "buy":
        vwap, vwhy = _vwap_buy(asks, size)
    elif side_l == "sell":
        vwap, vwhy = _vwap_sell(bids, size)
    else:
        msg = f"{_BLOCKED_LOG}: side ungueltig ({side!s})"
        raise InsufficientLiquidityError(
            msg,
            detail={"symbol": symbol, "side": side, "reason": "side_invalid"},
        )
    if vwap is None:
        msg = f"{_BLOCKED_LOG}: Tiefen-Nichtbedeckung in Top-{_TOPN_USE} ({vwhy!s}, symbol={symbol!s} size={size!s} side={side!s})"
        logger.warning("%s", msg)
        raise InsufficientLiquidityError(
            msg,
            detail={
                "symbol": symbol,
                "size": str(size),
                "side": side,
                "reason": vwhy or "insufficient",
            },
        )
    bps = _slippage_bps_vs_mid(mid=mid, vwap=vwap, side=side_l)
    if bps > cap:
        msg = (
            f"{_BLOCKED_LOG}: slippage {bps:.1f} bps > {cap!s} bps "
            f"(symbol={symbol!s} size={size!s} side={side_l} mid={format(mid, 'f')} vwap={format(vwap, 'f')})"
        )
        logger.warning("%s", msg)
        raise InsufficientLiquidityError(
            msg,
            detail={
                "symbol": symbol,
                "size": str(size),
                "side": side,
                "slippage_bps": str(bps),
                "cap_bps": str(cap),
                "mid": str(mid),
                "vwap": str(vwap),
            },
        )
