"""
TSFM / Apex: Fail-Closed-Status in Redis, damit signal_engine/risk_governor INFERENCE_TIMEOUT
sehen, ohne gRPC-Details zu publizieren.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("shared_py.inference_governance")

_STATE_TIMEOUT = "INFERENCE_TIMEOUT"
_REDIS_KEY_FMT = "inference:tsfm:governance:{symbol}"
_TTL_SEC_DEFAULT = 90


def _norm_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def redis_governance_key(symbol: str) -> str:
    return _REDIS_KEY_FMT.format(symbol=_norm_symbol(symbol) or "UNKNOWN")


def record_inference_timeout_state(redis_url: str, symbol: str, *, ttl_sec: int = _TTL_SEC_DEFAULT) -> None:
    if not (redis_url or "").strip() or not _norm_symbol(symbol):
        return
    try:
        from shared_py.redis_client import connect_sync_redis_with_init_backoff

        c = connect_sync_redis_with_init_backoff(redis_url, decode_responses=True)
        if c is None:
            return
        r = c[1]
    except Exception as exc:  # noqa: BLE001
        logger.debug("record inference timeout: redis %s", exc)
        return
    payload = json.dumps(
        {
            "state": _STATE_TIMEOUT,
            "fail_closed": True,
            "recorded_ts_ms": int(time.time() * 1000),
        },
        separators=(",", ":"),
    )
    try:
        r.set(redis_governance_key(symbol), payload, ex=ttl_sec)
    except Exception as exc:  # noqa: BLE001
        logger.debug("SET inference governance failed: %s", exc)


def read_inference_governance_state(redis_url: str, symbol: str) -> dict[str, Any] | None:
    if not (redis_url or "").strip() or not _norm_symbol(symbol):
        return None
    try:
        from shared_py.redis_client import connect_sync_redis_with_init_backoff

        c = connect_sync_redis_with_init_backoff(redis_url, decode_responses=True)
        if c is None:
            return None
        r = c[1]
    except Exception:
        return None
    try:
        raw = r.get(redis_governance_key(symbol))
    except Exception:  # noqa: BLE001
        return None
    if not raw or not str(raw).strip():
        return None
    try:
        j = json.loads(str(raw))
    except json.JSONDecodeError:
        return None
    return j if isinstance(j, dict) else None


def live_broker_payload_inference_blocks_trading(payload: dict[str, Any] | None) -> bool:
    """
    True, wenn Live-Execution (fail-closed) wegen TimesFM / Apex wegfaellt.
    """
    if not isinstance(payload, dict):
        return False
    u = payload.get("governor_universal_hard_block_reasons_json") or []
    for x in u:
        if str(x).strip() == "INFERENCE_TIMEOUT":
            return True
    sp = payload.get("source_snapshot") or {}
    if isinstance(sp, str) and sp.strip():
        try:
            sp = json.loads(sp)
        except json.JSONDecodeError:
            sp = {}
    if not isinstance(sp, dict):
        sp = {}
    ig = sp.get("inference_governance")
    if isinstance(ig, dict) and str(ig.get("state") or "") == _STATE_TIMEOUT:
        return True
    return bool(payload.get("inference_governance_unavailable"))


def merge_governance_into_source_snapshot(
    *,
    redis_url: str | None,
    symbol: str,
    source_snapshot: dict[str, Any],
) -> None:
    g = read_inference_governance_state(redis_url or "", symbol) if redis_url else None
    if not g:
        return
    st = str(g.get("state") or "").strip()
    if st == _STATE_TIMEOUT:
        source_snapshot["inference_governance"] = {
            "state": _STATE_TIMEOUT,
            "fail_closed": bool(g.get("fail_closed", True)),
            "recorded_ts_ms": g.get("recorded_ts_ms"),
        }
