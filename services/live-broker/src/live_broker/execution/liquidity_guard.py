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
            if not isinstance(item, list | tuple) or len(item) < 2:
                continue
            p, s = _dec(item[0]), _dec(item[1])
            if p > 0 and s > 0:
                out.append((p, s))
        if reverse:
            out.sort(key=lambda t: t[0], reverse=True)
        return out

    # Bids: bestes (hoechstes) zuerst; Asks: bestes (niedrigstes) zuerst
    return _one_side(raw_bids, reverse=True), _one_side(raw_asks, reverse=False)


def _mid_price(
    bids: list[tuple[Decimal, Decimal]], asks: list[tuple[Decimal, Decimal]]
) -> Decimal:
    if not bids or not asks:
        return Decimal("0")
    return (bids[0][0] + asks[0][0]) / Decimal("2")


def _vwap_buy(
    asks: list[tuple[Decimal, Decimal]], size: Decimal
) -> tuple[Decimal | None, str | None]:
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
    else:
        diff = mid - vwap
    ratio = diff / mid
    return ratio * Decimal("10000")


# --- Prometeus Metric & Global Halt Latch Fallback ---

# Globale Counter-Variable (Mock / Fallback fuer Prometheus falls die prometheus_client Bibliothek fehlt)
leverage_violation_counter = 0

try:
    from prometheus_client import Counter
    SECURITY_LEVERAGE_VIOLATION_ATTEMPTS_TOTAL = Counter(
        "security_leverage_violation_attempts_total",
        "Total number of uncompromisible preflight leverage violation attempts blocked.",
        ["symbol", "mode", "requested_leverage"]
    )
except ImportError:
    SECURITY_LEVERAGE_VIOLATION_ATTEMPTS_TOTAL = None


def verify_preflight_leverage(
    leverage: int,
    mode: str,
    *,
    symbol: str = "BTCUSDT",
    redis_url: str | None = None,
) -> bool:
    """
    Millisekundengenaue Preflight Hebel-Validierung.
    - STANDARD_FUTURES: Hard-cap maximal 11x Hebel.
    - BOT_GRID / BOT_DCA: Hard-cap maximal 22x Hebel.
    Gibt True zurück, falls Hebel gueltig ist.
    Falls ein Verstoss erkannt wird, loest die Funktion Alarm aus, erhoeht Prometheus Metriken,
    setzt den Redis-basierten global_halt_latch (Not-Aus) und gibt False zurück oder loest eine
    SecurityException aus.
    """
    mode_normalized = str(mode or "").strip().upper()
    cap = 22 if mode_normalized in ("BOT_GRID", "BOT_DCA") else 11

    if leverage > cap:
        global leverage_violation_counter
        leverage_violation_counter += 1
        
        logger.error(
            "CRITICAL SECURITY VIOLATION: Preflight leverage limit exceeded! "
            "Requested: %sx, Cap: %sx for mode: %s. Initiating EMERGENCY TERMINATION AND GLOBAL SHUTDOWN.",
            leverage,
            cap,
            mode_normalized,
        )

        # Prometheus-Metrik inkrementieren
        if SECURITY_LEVERAGE_VIOLATION_ATTEMPTS_TOTAL is not None:
            try:
                SECURITY_LEVERAGE_VIOLATION_ATTEMPTS_TOTAL.labels(
                    symbol=symbol,
                    mode=mode_normalized,
                    requested_leverage=str(leverage)
                ).inc()
            except Exception as exc:
                logger.warning("Failed to increment prometheus leverage violation metric: %s", exc)

        # Global Halt Latch auslösen (Redis Not-Aus setzen)
        if redis_url:
            try:
                # Importieren hier zur Vermeidung zirkulärer Importe
                from live_broker.global_halt_latch import publish_global_halt_state
                publish_global_halt_state(
                    redis_url,
                    active=True,
                )
                logger.critical("GLOBAL_HALT_LATCH successfully published to Redis due to leverage violation.")
            except Exception as exc:
                logger.critical(
                    "FAILED to trigger Global Halt Latch via publish_global_halt_state: %s. "
                    "System integrity compromised!",
                    exc,
                )

        return False

    return True


def check_preflight_liquidity(
    redis_pool_or_client: Any,
    symbol: str,
    *,
    size: Decimal,
    side: str,
    cap_bps: Decimal | None = None,
    max_orderbook_age_ms: int | float = 2000,
    now_ts_ms: int | float | None = None,
) -> Decimal:
    cap = cap_bps if cap_bps is not None else _DEFAULT_MAX_SLIPPAGE_BPS
    if cap < 0 or size <= 0:
        return Decimal("0")
    if side not in ("buy", "sell"):
        msg = f"{_BLOCKED_LOG}: side must be buy/sell, got {side!r}"
        raise InsufficientLiquidityError(msg)

    key = f"{ORDERBOOK_TOP5_REDIS_PREFIX}{symbol.upper()}"
    raw: Any = None
    try:
        if hasattr(redis_pool_or_client, "get") and not hasattr(
            redis_pool_or_client, "from_url"
        ):
            raw = redis_pool_or_client.get(key)
        else:
            r = sync_redis_from_pool(redis_pool_or_client)
            raw = r.get(key)
    except Exception as exc:
        msg = f"{_BLOCKED_LOG}: Redis read failure key={key} err={exc}"
        raise InsufficientLiquidityError(msg) from exc

    if not raw:
        msg = f"{_BLOCKED_LOG}: kein Ticks-Eintrag in Redis fuer key={key}"
        raise InsufficientLiquidityError(msg)

    try:
        doc = json.loads(raw)
    except Exception as exc:
        msg = f"{_BLOCKED_LOG}: JSON-Parse Fehler fuer key={key} raw={raw!r}"
        raise InsufficientLiquidityError(msg) from exc

    if not isinstance(doc, dict):
        msg = f"{_BLOCKED_LOG}: ungueltiges Format in Redis fuer key={key}"
        raise InsufficientLiquidityError(msg)

    raw_b = doc.get("bids")
    raw_a = doc.get("asks")
    snap_ts = doc.get("ts_ms") or doc.get("timestamp_ms") or doc.get("ts")
    if max_orderbook_age_ms > 0:
        if now_ts_ms is None:
            import time
            now_ts_ms = int(time.time() * 1000)
        if snap_ts in (None, ""):
            msg = f"{_BLOCKED_LOG}: Zeitstempel fehlt im Orderbuch key={key}"
            raise InsufficientLiquidityError(
                msg,
                detail={
                    "symbol": symbol,
                    "side": side,
                    "reason": "orderbook_timestamp_missing",
                },
            )
        age_ms = int(now_ts_ms - int(snap_ts))
        if age_ms > int(max_orderbook_age_ms):
            msg = (
                f"{_BLOCKED_LOG}: orderbook stale "
                f"(age_ms={age_ms} > {max_orderbook_age_ms}, "
                f"symbol={symbol!s})"
            )
            raise InsufficientLiquidityError(
                msg,
                detail={
                    "symbol": symbol,
                    "side": side,
                    "reason": "orderbook_stale",
                    "age_ms": age_ms,
                    "max_orderbook_age_ms": int(max_orderbook_age_ms),
                },
            )
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
        msg = (
            f"{_BLOCKED_LOG}: Tiefen-Nichtbedeckung in Top-{_TOPN_USE} "
            f"({vwhy!s}, symbol={symbol!s} size={size!s} side={side!s})"
        )
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
            f"(symbol={symbol!s} size={size!s} side={side_l} "
            f"mid={format(mid, 'f')} vwap={format(vwap, 'f')})"
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
    return bps


class _InlineOrderbookRedis:
    """Test-/Inline-Snapshot ohne Redis-Pool."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self._raw = json.dumps(snapshot)

    def get(self, _key: str) -> str | None:
        return self._raw


def verify_execution_liquidity(
    symbol: str,
    size: Decimal,
    side: str,
    redis_url: str,
    *,
    max_slippage_bps: Decimal | None = None,
    strict: bool = False,
    now_ts_ms: int | float | None = None,
    max_orderbook_age_ms: int | float = 2000,
    _snapshot: dict[str, Any] | None = None,
) -> Decimal | None:
    """
    Order-Submit-Pfad: prueft Top-5-Liquiditaet vor Market-Orders.
    Gibt Slippage in bps zurueck oder None wenn Guard deaktiviert (non-strict, kein Redis).
    """
    cap = max_slippage_bps if max_slippage_bps is not None else _DEFAULT_MAX_SLIPPAGE_BPS
    if _snapshot is not None:
        effective_now = now_ts_ms
        if effective_now is None:
            snap_ts = (
                _snapshot.get("ts_ms")
                or _snapshot.get("timestamp_ms")
                or _snapshot.get("ts")
            )
            if snap_ts not in (None, ""):
                effective_now = int(snap_ts)
        return check_preflight_liquidity(
            _InlineOrderbookRedis(_snapshot),
            symbol,
            size=size,
            side=side,
            cap_bps=cap,
            max_orderbook_age_ms=max_orderbook_age_ms,
            now_ts_ms=effective_now,
        )
    url = (redis_url or "").strip()
    if not url:
        if strict:
            msg = f"{_BLOCKED_LOG}: redis_url fehlt (strict=True)"
            raise InsufficientLiquidityError(msg)
        return None
    pool = create_sync_connection_pool(url)
    return check_preflight_liquidity(
        pool,
        symbol,
        size=size,
        side=side,
        cap_bps=cap,
        max_orderbook_age_ms=max_orderbook_age_ms,
        now_ts_ms=now_ts_ms,
    )
