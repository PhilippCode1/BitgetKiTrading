"""
Optional: LLM-Anreicherung ueber llm-orchestrator /llm/news_summary.

Kein direkter Provider-Call — nur HTTP zum Orchestrator.

Trading-Kern: Die finale Relevanz bleibt immer an die regelbasierte Basis gekoppelt
(`clamp_llm_relevance`: hoechstens +- NEWS_SCORE_MAX_LLM_DELTA). Ohne gueltige
Regelbasis kann das LLM die Freigabe nicht allein tragen; Sentiment/Impact aus
dem LLM greifen nur bei ausreichender LLM-Confidence.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from news_engine.config import NewsEngineSettings
from news_engine.scoring.rules_v1 import Scored
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

logger = logging.getLogger("news_engine.llm_enricher")


def clamp_llm_relevance(rule_score: int, llm_score: int, max_delta: int) -> int:
    lo = max(0, rule_score - max_delta)
    hi = min(100, rule_score + max_delta)
    return max(lo, min(hi, llm_score))


def sentiment_from_neg1(v: float) -> str:
    if v > 0.25:
        return "bullisch"
    if v < -0.25:
        return "baerisch"
    if -0.15 <= v <= 0.15:
        return "neutral"
    return "mixed"


def fetch_llm_news_summary(
    settings: NewsEngineSettings,
    *,
    title: str,
    description: str | None,
    content: str | None,
    url: str,
    source: str,
    published_ts_ms: int | None,
) -> dict[str, Any] | None:
    base = settings.llm_orch_base_url.rstrip("/")
    pref = settings.news_llm_provider_pref or "auto"
    body = {
        "title": title,
        "description": description,
        "content": content,
        "url": url,
        "source": source,
        "published_ts_ms": published_ts_ms,
        "provider_preference": pref,
        "temperature": 0.2,
    }
    try:
        headers = {"Accept": "application/json"}
        if settings.service_internal_api_key:
            headers[INTERNAL_SERVICE_HEADER] = settings.service_internal_api_key
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{base}/llm/news_summary", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("llm news_summary fehlgeschlagen: %s", exc)
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        logger.warning("llm news_summary ungueltige Antwort")
        return None
    result = data.get("result")
    if not isinstance(result, dict):
        return None
    prov = data.get("provenance")
    if isinstance(prov, dict):
        out = dict(result)
        out["_orchestrator_provenance"] = prov
        return out
    return result


def merge_llm_with_rules(
    rule: Scored,
    llm: dict[str, Any],
    *,
    max_delta: int,
    min_confidence: float = 0.4,
) -> tuple[Scored, dict[str, Any]]:
    """
    Wendet Relevanz-Clamp an; Sentiment/Impact nur bei ausreichender LLM-Confidence.

    Die Handelslogik darf nicht ausschliesslich auf dem LLM-Ergebnis beruhen:
    `relevance` wird immer innerhalb [rule-max_delta, rule+max_delta] gehalten.
    """
    conf = float(llm.get("confidence_0_1") or 0.0)
    rs_llm = llm.get("relevance_score_0_100")
    try:
        rs_int = int(rs_llm) if rs_llm is not None else rule.relevance
    except (TypeError, ValueError):
        rs_int = rule.relevance

    relevance = clamp_llm_relevance(rule.relevance, rs_int, max_delta)

    sentiment = rule.sentiment
    impact = rule.impact_window
    if conf >= min_confidence:
        sn = llm.get("sentiment_neg1_to_1")
        try:
            if sn is not None:
                sentiment = sentiment_from_neg1(float(sn))
        except (TypeError, ValueError):
            pass
        iw = llm.get("impact_window")
        if isinstance(iw, str) and iw in ("sofort", "mittel", "langsam"):
            impact = iw

    return (
        Scored(relevance=relevance, sentiment=sentiment, impact_window=impact),
        llm,
    )


def build_entities_json(llm: dict[str, Any]) -> list[Any] | None:
    ent = llm.get("entities_mentioned")
    if isinstance(ent, list):
        return ent
    return None
