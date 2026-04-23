"""Verhindert Endlosschleifen: Self-Healing-Reaktionen auf eigene Folge-Events."""

from __future__ import annotations

import logging
from typing import Any

from redis import Redis

logger = logging.getLogger("learning_engine.self_healing.recursion")


def _payload_origin(details: dict[str, Any]) -> str:
    o = details.get("self_healing_origin") or details.get("origin") or ""
    return str(o).strip().lower()


def should_skip_for_recursion(details: dict[str, Any]) -> bool:
    o = _payload_origin(details)
    if o in ("self_healing_pipeline", "self_healing_apply", "learning_engine_self_healing"):
        return True
    if details.get("self_healing_depth") is not None:
        try:
            if int(details["self_healing_depth"]) >= 2:
                return True
        except (TypeError, ValueError):
            pass
    return False


def reserve_alert_processing(
    redis_url: str,
    dedupe_key: str | None,
    *,
    ttl_sec: int = 3600,
) -> bool:
    """
    Atomar: nur ein Worker verarbeitet dieselbe logische Dedupe-ID pro Zeitfenster.

    Returns False wenn bereits reserviert (andere oder gleiche Instanz).
    """
    if not dedupe_key:
        return True
    key = f"self_healing:reserved:{dedupe_key}"[:512]
    try:
        r = Redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
        ok = bool(r.set(key, "1", nx=True, ex=ttl_sec))
        r.close()
        return ok
    except Exception as exc:
        logger.warning("reserve_alert_processing redis failed: %s", exc)
        return True
