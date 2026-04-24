"""
Dynamische War-Room-Gewichte aus learning-engine (AI Precision pro Regim, Prompt 29).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from llm_orchestrator.config import LLMOrchestratorSettings

# Gleiche IDs wie in war_room (kein Import: Zyklen vermeiden)
MACRO_ID = "macro_analyst"
QUANT_ID = "quant_analyst"
RISK_ID = "risk_governor"

logger = logging.getLogger("llm_orchestrator.consensus.specialist_precision")

_DEFAULT_P = 0.6
_AGENT_IDS = (MACRO_ID, QUANT_ID, RISK_ID)


def extract_market_regime(market_event: dict[str, Any] | None) -> str:
    if not isinstance(market_event, dict):
        return "unknown"
    for k in (
        "market_regime",
        "regime_state",
        "regime_label",
        "volatility_regime",
    ):
        v = market_event.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    srow = market_event.get("signal_row")
    if isinstance(srow, dict):
        for k in ("market_regime", "regime_state", "regime_label"):
            v = srow.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return "unknown"


def precision_stake_multiplier(ai_precision_0_1: float) -> float:
    """Stimmgewicht-Faktor: >70% -> 1.5, <50% -> 0.5, sonst 1.0 (Prompt 29)."""
    try:
        p = float(ai_precision_0_1)
    except (TypeError, ValueError):
        p = _DEFAULT_P
    if p > 0.7:
        return 1.5
    if p < 0.5:
        return 0.5
    return 1.0


def _default_precision_map() -> dict[str, float]:
    return {a: _DEFAULT_P for a in _AGENT_IDS}


def precision_0_1_by_agent(body: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(body, dict):
        return _default_precision_map()
    sp = body.get("specialists")
    if not isinstance(sp, dict):
        return _default_precision_map()
    for aid in _AGENT_IDS:
        row = sp.get(aid)
        if not isinstance(row, dict):
            out[aid] = _DEFAULT_P
            continue
        try:
            out[aid] = float(row.get("ai_precision_0_1", _DEFAULT_P))
        except (TypeError, ValueError):
            out[aid] = _DEFAULT_P
    return out


def fetch_specialist_precision_block(
    settings: LLMOrchestratorSettings, *, market_regime: str
) -> dict[str, Any]:
    """
    JSON-Antwort der learning-engine (oder Fallback bei Fehler/Disabled).
    """
    if not getattr(settings, "war_room_fetch_specialist_precision", True):
        return {
            "status": "disabled",
            "market_regime": market_regime,
            "schema": "war_room_specialist_precision_v1",
            "specialists": {a: {"ai_precision_0_1": _DEFAULT_P, "source": "disabled"} for a in _AGENT_IDS},
        }
    base = (settings.learning_engine_base_url or "").rstrip("/")
    if not base:
        return {
            "status": "error",
            "market_regime": market_regime,
            "schema": "war_room_specialist_precision_v1",
            "specialists": {
                a: {"ai_precision_0_1": _DEFAULT_P, "source": "no_learning_base_url"} for a in _AGENT_IDS
            },
        }
    url = f"{base}/learning/war-room/specialist-ai-precision"
    params = {"market_regime": market_regime or "unknown"}
    tmo = float(getattr(settings, "war_room_specialist_precision_timeout_sec", 2.0) or 2.0)
    try:
        with httpx.Client(timeout=tmo) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
        logger.warning("war_room: specialist precision GET failed: %s", exc)
        return {
            "status": "error",
            "market_regime": market_regime,
            "schema": "war_room_specialist_precision_v1",
            "note_de": f"HTTP-Fetch fehlgeschlagen: {type(exc).__name__}",
            "specialists": {
                a: {"ai_precision_0_1": _DEFAULT_P, "source": "fetch_error_fallback"} for a in _AGENT_IDS
            },
        }
    if not isinstance(data, dict):
        return {
            "status": "error",
            "market_regime": market_regime,
            "specialists": {
                a: {"ai_precision_0_1": _DEFAULT_P, "source": "invalid_json"} for a in _AGENT_IDS
            },
        }
    return data


def apply_precision_to_weights(
    base_weights: dict[str, float], precision_0_1: dict[str, float]
) -> dict[str, float]:
    """
    Skaliert Basis-Stimmen mit Precision-Multiplikatoren, gleiche Semantik wie
    urspruengliche `base_weights` (Makro/Quant/Risk bleiben alle Keys).
    """
    w: dict[str, float] = {}
    for k, v0 in base_weights.items():
        try:
            b = float(v0)
        except (TypeError, ValueError):
            b = 0.0
        p = precision_0_1.get(k, _DEFAULT_P) if isinstance(precision_0_1, dict) else _DEFAULT_P
        w[k] = b * precision_stake_multiplier(p)
    return w


def log_weighted_stakes_pre_consensus(
    *,
    market_regime: str,
    base_weights: dict[str, float],
    precision_0_1: dict[str, float],
    adjusted_weights_unnormalized: dict[str, float],
) -> None:
    """DoD: gewichtete Stimmen / Multiplikatoren vor Konsens-Score."""
    parts: list[str] = []
    for aid in (MACRO_ID, QUANT_ID, RISK_ID):
        p = float(precision_0_1.get(aid) or _DEFAULT_P)
        m = precision_stake_multiplier(p)
        b0 = float((base_weights or {}).get(aid) or 0.0)
        wu = float((adjusted_weights_unnormalized or {}).get(aid) or 0.0)
        parts.append(
            f"{aid}: precision_0_1={p:.3f} mult={m:.1f} base_stake={b0:.3f} adjusted_stake={wu:.3f}"
        )
    line = f"regime={market_regime!r} | " + " | ".join(parts)
    logger.info("war_room weighted_stakes pre_consensus: %s", line)
    # Zusaetzlich strukturiert fürs Log-Aggregat (eine JSON-Zeile, optional parsbar)
    try:
        logger.info(
            "war_room weighted_stakes pre_consensus_json: %s",
            json.dumps(
                {
                    "market_regime": market_regime,
                    "agents": {
                        aid: {
                            "ai_precision_0_1": float(precision_0_1.get(aid) or _DEFAULT_P),
                            "stake_multiplier": precision_stake_multiplier(
                                float(precision_0_1.get(aid) or _DEFAULT_P)
                            ),
                            "base_weight": float((base_weights or {}).get(aid) or 0.0),
                            "adjusted_stake": float(
                                (adjusted_weights_unnormalized or {}).get(aid) or 0.0
                            ),
                        }
                        for aid in _AGENT_IDS
                    },
                },
                ensure_ascii=False,
            ),
        )
    except (TypeError, ValueError):
        pass
