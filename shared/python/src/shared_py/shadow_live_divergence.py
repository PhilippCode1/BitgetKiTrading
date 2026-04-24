"""Shadow-vs-Live-Divergenz (Prompt 28): messbare Abgleichslogik fuer Live-Freigabe.

Die Funktion ist rein deterministisch; Live-Broker entscheidet separat, ob Verletzungen
Live-Candidates blockieren (REQUIRE_SHADOW_MATCH_BEFORE_LIVE).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("shared_py.shadow_live_divergence")


SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION = "p28-v1"


@dataclass(frozen=True)
class ShadowLiveThresholds:
    """Vergleichsschwellen; dokumentiert in docs/shadow_live_divergence.md."""

    max_timing_skew_ms: int = 180_000
    max_leverage_delta: int = 0
    max_signal_shadow_divergence_0_1: float = 0.15
    timing_violation_hard: bool = False
    max_slippage_expectation_bps: float | None = None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_slippage_bps(
    exit_preview: dict[str, Any] | None,
    signal_payload: dict[str, Any],
) -> float | None:
    v = _coerce_float(signal_payload.get("slippage_bps_entry"))
    if v is not None:
        return v
    if not exit_preview or not isinstance(exit_preview, dict):
        return None
    sp = exit_preview.get("stop_plan")
    if isinstance(sp, dict):
        ex = sp.get("execution")
        if isinstance(ex, dict):
            s = _coerce_float(ex.get("estimated_slippage_bps"))
            if s is not None:
                return s
    return None


def assess_shadow_live_divergence(
    *,
    shadow_decision: tuple[str, str],
    live_decision: tuple[str, str],
    signal_payload: dict[str, Any],
    risk_decision: dict[str, Any],
    intent_leverage: int | None,
    now_ms: int,
    exit_preview: dict[str, Any] | None,
    thresholds: ShadowLiveThresholds,
) -> dict[str, Any]:
    """Vergleicht simulierten Shadow-Pfad mit Live-Pfad plus Signal-/Risk-Dimensionen.

    **Harte Verletzungen** (match_ok=false) — Live darf bei aktivem Gate nicht als Candidate:
    - Shadow-Pfad ``blocked``, Live-Pfad ``live_candidate_recorded``
    - Signal-``trade_action`` weicht von Risk-``trade_action`` ab
    - Hebel-Delta (Intent vs. empfohlen) > ``max_leverage_delta``
    - Intent-Hebel > Signal-``allowed_leverage``
    - ``shadow_divergence_0_1`` aus Signal > Schwelle (Modell vs. Heuristik)
    - Slippage-Erwartung > Cap, falls Cap gesetzt
    - Timing-Skew > ``max_timing_skew_ms``, wenn ``timing_violation_hard``

    **Weiche Verletzungen** — nur Metrik/Monitoring, kein Gate (ausser Hard-Flag oben).
    """
    shadow_action, shadow_reason = shadow_decision
    live_action, live_reason = live_decision
    hard: list[str] = []
    soft: list[str] = []
    dimensions: dict[str, Any] = {
        "shadow_path_action": shadow_action,
        "shadow_path_reason": shadow_reason,
        "live_path_action": live_action,
        "live_path_reason": live_reason,
    }

    if shadow_action == "blocked" and live_action == "live_candidate_recorded":
        hard.append("shadow_live_shadow_blocked_live_candidate")

    sa = str(signal_payload.get("trade_action") or "").strip().lower()
    ra = str(risk_decision.get("trade_action") or "").strip().lower()
    dimensions["signal_trade_action"] = sa or None
    dimensions["risk_trade_action"] = ra or None
    if sa and ra and sa != ra:
        hard.append("signal_risk_trade_action_mismatch")

    lev = intent_leverage
    rec = _parse_int(signal_payload.get("recommended_leverage"))
    allow = _parse_int(signal_payload.get("allowed_leverage"))
    dimensions["intent_leverage"] = lev
    dimensions["signal_recommended_leverage"] = rec
    dimensions["signal_allowed_leverage"] = allow

    if lev is not None and allow is not None and lev > allow:
        hard.append("intent_leverage_exceeds_signal_allowed")

    if lev is not None and rec is not None:
        delta = abs(lev - rec)
        dimensions["leverage_delta"] = delta
        if delta > thresholds.max_leverage_delta:
            hard.append("leverage_delta_exceeds")

    sd = _coerce_float(signal_payload.get("shadow_divergence_0_1"))
    dimensions["signal_shadow_divergence_0_1"] = sd
    if sd is not None and sd > thresholds.max_signal_shadow_divergence_0_1:
        hard.append("signal_shadow_model_divergence_high")

    analysis_ts = _parse_int(signal_payload.get("analysis_ts_ms"))
    dimensions["analysis_ts_ms"] = analysis_ts
    if analysis_ts is not None and analysis_ts > 0:
        skew = now_ms - analysis_ts
        dimensions["timing_skew_ms"] = skew
        if skew > thresholds.max_timing_skew_ms:
            if thresholds.timing_violation_hard:
                hard.append("timing_skew_exceeds_hard")
            else:
                soft.append("timing_skew_exceeds_soft")

    slip = _extract_slippage_bps(exit_preview, signal_payload)
    dimensions["estimated_slippage_bps"] = slip
    cap = thresholds.max_slippage_expectation_bps
    if cap is not None and slip is not None and slip > cap:
        hard.append("slippage_expectation_exceeds_cap")

    return {
        "protocol_version": SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION,
        "match_ok": len(hard) == 0,
        "hard_violations": hard,
        "soft_violations": soft,
        "dimensions": dimensions,
        "thresholds_applied": {
            "max_timing_skew_ms": thresholds.max_timing_skew_ms,
            "max_leverage_delta": thresholds.max_leverage_delta,
            "max_signal_shadow_divergence_0_1": thresholds.max_signal_shadow_divergence_0_1,
            "timing_violation_hard": thresholds.timing_violation_hard,
            "max_slippage_expectation_bps": thresholds.max_slippage_expectation_bps,
        },
    }


# --- Shadow-Match-Latch (REQUIRE_SHADOW_MATCH_BEFORE_LIVE): externer Redis-Beweis ---

SHADOW_MATCH_REDIS_PREFIX = "shadow:match:"
DEFAULT_SHADOW_MATCH_LATCH_TIMEOUT_MS = 500
DEFAULT_SHADOW_MATCH_REDIS_TTL_SEC = 300
SHADOW_MATCH_LATCH_VALUE = "1"


def shadow_match_latch_redis_key(execution_id: str) -> str:
    """Redis-Key Live-Broker/Paper: ``shadow:match:{execution_id}`` (UUID, gemeinsam mit live.execution_decisions)."""
    e = str(execution_id).strip()
    if not e:
        return SHADOW_MATCH_REDIS_PREFIX
    return f"{SHADOW_MATCH_REDIS_PREFIX}{e}"


def parse_prebound_execution_id(
    *,
    signal_payload: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    trace: dict[str, Any] | None,
) -> str | None:
    """
    Muss in Signal/Live-Intent vorkommen, bevor der Paper-Shadow-Preis-Trade dieselbe
    :func:`shadow_match_latch_redis_key` setzen kann. Reihenfolge: gleiche UUID in paper + live.
    """
    for bag in (payload or {}, trace or {}, (signal_payload or {})):
        if not isinstance(bag, dict):
            continue
        for k in (
            "execution_id",
            "prebound_execution_id",
            "correlation_execution_id",
        ):
            raw = bag.get(k)
            if raw in (None, ""):
                continue
            s = str(raw).strip()
            if not s:
                continue
            try:
                uuid.UUID(s)
            except (ValueError, TypeError, AttributeError):
                continue
            return s
    return None


def set_shadow_match_latch(
    redis_url: str,
    execution_id: str,
    *,
    ttl_sec: int = DEFAULT_SHADOW_MATCH_REDIS_TTL_SEC,
) -> bool:
    """
    Wird von der Shadow-/Paper-Engine aufgerufen, nachdem die Simulation (Demo) erfolgreich war.
    Returns False wenn kein Redis oder Set fehlschlaegt (kein harter Fehler in Paper-Open).
    """
    u = (redis_url or "").strip()
    if not u or not (execution_id or "").strip():
        return False
    key = shadow_match_latch_redis_key(execution_id)
    try:
        import redis as _redis
    except ImportError:  # pragma: no cover
        return False
    try:
        r = _redis.Redis.from_url(
            u, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        r.set(key, SHADOW_MATCH_LATCH_VALUE, ex=max(1, int(ttl_sec)))
        return True
    except Exception:
        return False


def get_shadow_match_latch_present(redis_url: str, execution_id: str) -> bool:
    u = (redis_url or "").strip()
    if not u or not (execution_id or "").strip():
        return False
    key = shadow_match_latch_redis_key(execution_id)
    try:
        import redis as _redis
    except ImportError:  # pragma: no cover
        return False
    try:
        r = _redis.Redis.from_url(
            u, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        v = r.get(key)
        return v is not None and str(v) != ""
    except Exception:
        return False


def get_shadow_match_latch_read_status(redis_url: str, execution_id: str) -> str:
    """
    Lesezustand fuer Live-Gating: ``present`` | ``absent`` | ``redis_unavailable``.

    ``redis_unavailable`` = Verbindung/Timeout (Fail-Closed: kein stilles "Key fehlt").
    """
    u = (redis_url or "").strip()
    eid = (execution_id or "").strip()
    if not u or not eid:
        return "absent"
    key = shadow_match_latch_redis_key(eid)
    try:
        import redis as _redis
    except ImportError:  # pragma: no cover
        return "redis_unavailable"
    r = None
    v: Any = None
    try:
        r = _redis.Redis.from_url(
            u, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        v = r.get(key)
    except (OSError, _redis.exceptions.ConnectionError, _redis.exceptions.TimeoutError) as exc:
        logger.warning("shadow_match_latch: redis read failed: %s", exc)
        return "redis_unavailable"
    except Exception as exc:  # noqa: BLE001
        logger.warning("shadow_match_latch: redis read unexpected: %s", exc)
        return "redis_unavailable"
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:  # noqa: BLE001
                pass
    if v is not None and str(v) != "":
        return "present"
    return "absent"


def wait_for_shadow_match_latch(
    redis_url: str,
    execution_id: str,
    *,
    timeout_ms: int = DEFAULT_SHADOW_MATCH_LATCH_TIMEOUT_MS,
    poll_ms: int = 25,
) -> dict[str, Any]:
    """
    Live-Broker: Wartet auf Redis-Key ``shadow:match:{execution_id}`` (enges Fenster).
    Ohne Key nach ``timeout_ms``: ``ok=false`` (kein Echtgeld-Submit hinterher).
    """
    u = (redis_url or "").strip()
    t0 = time.monotonic()
    if not u or not (execution_id or "").strip():
        return {
            "ok": False,
            "waited_ms": 0,
            "key": shadow_match_latch_redis_key(execution_id or ""),
            "error": "redis_or_execution_id_missing",
        }
    key = shadow_match_latch_redis_key(execution_id)
    limit_ms = max(0, int(timeout_ms))
    poll = max(1, min(100, int(poll_ms)))
    last_err: str | None = None
    try:
        import redis as _redis
    except ImportError as exc:  # pragma: no cover
        return {
            "ok": False,
            "waited_ms": 0,
            "key": key,
            "error": f"redis_import:{exc!s}",
        }
    r = _redis.Redis.from_url(
        u, decode_responses=True, socket_connect_timeout=1, socket_timeout=2
    )
    end_mono = t0 + limit_ms / 1000.0
    while time.monotonic() < end_mono:
        try:
            v = r.get(key)
            if v is not None and str(v) != "":
                waited = (time.monotonic() - t0) * 1000.0
                return {"ok": True, "waited_ms": int(waited), "key": key}
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)[:200]
        if time.monotonic() + (poll / 1000.0) < end_mono:
            time.sleep(poll / 1000.0)
    waited = (time.monotonic() - t0) * 1000.0
    return {
        "ok": False,
        "waited_ms": int(min(waited, float(limit_ms) + 50)),
        "key": key,
        "error": last_err or "shadow_match_key_absent",
    }
