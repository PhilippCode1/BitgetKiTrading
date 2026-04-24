"""
VPIN-Score (0..1) aus Redis fuer Toxic-Flow-Guards (Live-Submission, Risk-Governor-Paritaet).

Key-Schema: ``market:vpin_score:{SYMBOL}`` (Symbol upper, z. B. BTCUSDT; String-Float).
Fehlender Key / Parse-Fehler: ``None`` (kein Zwangsschritt, Guard optional).
"""

from __future__ import annotations

import logging
from typing import Any

from shared_py.redis_client import get_or_create_sync_pooled_client

logger = logging.getLogger("shared_py.observability.vpin_redis")

# Live-Broker Risk-Adapter + Signal-Governor: identische Schwellen (Toxic-Flow-Guard)
VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1 = 0.7
VPIN_HARD_HALT_THRESHOLD_0_1 = 0.85

VPIN_REDIS_KEY_FMT = "market:vpin_score:{symbol}"


def market_vpin_score_redis_key(symbol: str) -> str:
    s = str(symbol or "").strip().upper()
    return VPIN_REDIS_KEY_FMT.format(symbol=s or "UNKNOWN")


def _parse_0_1(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def read_market_vpin_score_0_1(redis_url: str, symbol: str) -> float | None:
    """
    Liest den zuletzt bekannten VPIN-Score fuer das Symbol. Keine Exceptions nach aussen
    (Netz/Redis: None).
    """
    u = (redis_url or "").strip()
    if not u:
        return None
    key = market_vpin_score_redis_key(symbol)
    try:
        r = get_or_create_sync_pooled_client(u, role="market_vpin_score")
        raw = r.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("read_market_vpin_score_0_1 %s: %s", key, exc)
        return None
    return _parse_0_1(raw)
