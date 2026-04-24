"""
War-Room: AI-Precision je Spezialist pro Marktregim (Prompt 20 / 29).

V1: regime-basierte Heuristik (keine DB-Abfrage) — Werte sind relative
 historische Erwartung (hohe Volatilitaet -> Quant stärker, Range -> Risk/Macro anders).
 Später: Ersetzung durch Aggregat aus learn.* (E2E / Outcomes pro Regim).
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter

def _norm_regime(s: str | None) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"[^a-z0-9_]+", "_", t)
    return t or "unknown"


# Heuristik: ai_precision_0_1 in [0,1] (entspricht "Trefferquote"-Proxys)
_HEUR: dict[str, dict[str, float]] = {
    "high_vol": {
        "macro_analyst": 0.44,
        "quant_analyst": 0.78,
        "risk_governor": 0.68,
    },
    "volatile": {
        "macro_analyst": 0.44,
        "quant_analyst": 0.78,
        "risk_governor": 0.68,
    },
    "trending": {
        "macro_analyst": 0.58,
        "quant_analyst": 0.64,
        "risk_governor": 0.58,
    },
    "trend": {
        "macro_analyst": 0.58,
        "quant_analyst": 0.64,
        "risk_governor": 0.58,
    },
    "range": {
        "macro_analyst": 0.52,
        "quant_analyst": 0.55,
        "risk_governor": 0.62,
    },
    "unknown": {
        "macro_analyst": 0.60,
        "quant_analyst": 0.60,
        "risk_governor": 0.60,
    },
}

_DEFAULT = _HEUR["unknown"]


def _precision_row(regime_key: str) -> dict[str, Any]:
    base = _HEUR.get(regime_key) or _DEFAULT
    out: dict[str, Any] = {}
    for k, v in base.items():
        out[k] = {
            "ai_precision_0_1": float(v),
            "source": "regime_heuristic_v1",
        }
    return {
        "status": "ok",
        "market_regime": regime_key,
        "schema": "war_room_specialist_precision_v1",
        "specialists": out,
    }


def build_war_room_precision_router() -> APIRouter:
    r = APIRouter(tags=["learning", "war_room"])

    @r.get("/learning/war-room/specialist-ai-precision")
    def specialist_ai_precision(
        market_regime: str | None = None,
    ) -> dict[str, Any]:
        """
        Liefert **AI Precision**-Proxys (0..1) pro War-Room-Spezialist für das Regime.

        V1-Quelle: `regime_heuristic_v1` (Prompt 29). Eine spätere Version kann
        `source: e2e_aggregate` aus der Datenbank liefern.
        """
        raw = _norm_regime(market_regime)
        if raw in _HEUR:
            key = raw
        elif "high" in raw and "vol" in raw:
            key = "high_vol"
        elif "vol" in raw or "volatile" in raw:
            key = "volatile"
        elif "trend" in raw or "bull" in raw or "bear" in raw:
            key = "trending"
        elif "range" in raw or "flat" in raw or "chop" in raw:
            key = "range"
        else:
            key = "unknown"
        return _precision_row(key)

    return r
