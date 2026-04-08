"""
Strukturierter Marktkontext: News/Makro/Listing/Funding/Struktur/Exchange — instrument- und playbook-sensitiv.

Deterministisch, kein LLM. LLM-Anteile in News duerfen die DB-Felder (relevance, sentiment, impact_window)
beeinflussen; diese Schicht interpretiert nur gespeicherte Fakten + Text-Heuristiken.

Siehe docs/structured_market_context.md
"""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

STRUCTURED_MARKET_CONTEXT_VERSION = "smc-v1"


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int | None:
    if x in (None, ""):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _norm_text(news_row: Mapping[str, Any] | None) -> str:
    if not news_row:
        return ""
    parts = [
        str(news_row.get("title") or ""),
        str(news_row.get("summary") or ""),
        str(news_row.get("body") or ""),
        str(news_row.get("text") or ""),
    ]
    raw = news_row.get("raw_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if isinstance(raw, dict):
        frag = raw.get("fragment")
        if isinstance(frag, dict):
            parts.append(str(frag.get("title") or ""))
            parts.append(str(frag.get("text") or ""))
    return " ".join(parts).lower()


def _published_ts_ms(news_row: Mapping[str, Any] | None) -> int | None:
    if not news_row:
        return None
    for key in ("published_ts_ms", "published_ts", "ingest_ts_ms"):
        v = _i(news_row.get(key))
        if v is not None and v > 0:
            return v
    return None


def _sentiment_0_1(news_row: Mapping[str, Any] | None) -> float | None:
    if not news_row:
        return None
    raw = news_row.get("sentiment")
    if raw in (None, ""):
        return None
    s = str(raw).strip().lower()
    if s in ("bullisch", "bullish", "positive"):
        return 0.65
    if s in ("baerisch", "bearish", "negative"):
        return -0.65
    if s in ("neutral", "mixed"):
        return 0.0
    v = _f(raw)
    if v is not None and -1.0 <= v <= 1.0:
        return float(v)
    return None


def _impact_immediate(impact_window: str | None) -> bool:
    if not impact_window:
        return False
    w = str(impact_window).strip().lower()
    return w in ("sofort", "immediate", "instant")


def _detect_facets(text: str) -> list[str]:
    facets: list[str] = []
    if any(
        k in text
        for k in (
            "listing",
            "lists on",
            "will list",
            "notierung",
            "neu notiert",
            "to list",
        )
    ):
        facets.append("listing")
    if "delist" in text or "remove pair" in text or "trading halt" in text:
        facets.append("delisting")
    if any(k in text for k in ("funding rate", "funding payment", "funding spike")):
        facets.append("funding_settlement")
    if any(
        k in text
        for k in (
            "delivery",
            "contract expiry",
            "contract expiration",
            "settlement date",
        )
    ):
        facets.append("delivery")
    if any(
        k in text
        for k in (
            "market open",
            "opening bell",
            "session open",
            "rth open",
            "europe open",
            "asia open",
        )
    ):
        facets.append("session_open")
    if any(
        k in text
        for k in (
            "cpi",
            "ppi",
            "nfp",
            "fed ",
            "ecb ",
            "fomc",
            "interest rate",
            "inflation",
            "gdp",
            "macro",
        )
    ):
        facets.append("macro")
    if any(k in text for k in ("btc dominance", "eth/btc", "correlation", "risk-off", "risk on")):
        facets.append("benchmark_correlation")
    if any(k in text for k in ("outage", "maintenance", "degraded", "withdrawal suspend")):
        facets.append("exchange_status")
    return facets


def _structure_break_hint(structure_events: list[Mapping[str, Any]] | None) -> bool:
    if not structure_events:
        return False
    for ev in structure_events[:12]:
        if not isinstance(ev, dict):
            continue
        st = str(ev.get("event_subtype") or ev.get("kind") or "").upper()
        if st == "CHOCH" or ev.get("choch") is True:
            return True
    return False


def _instrument_context_key(symbol: str, market_family: str) -> str:
    sym = str(symbol or "").upper()
    mf = str(market_family or "").strip().lower()
    if "BTC" in sym:
        return f"btc_{mf or 'unknown'}"
    if "ETH" in sym:
        return f"eth_{mf or 'unknown'}"
    if mf == "spot":
        return "alt_spot"
    if mf == "margin":
        return "alt_margin"
    if mf == "futures":
        return "alt_futures"
    return f"other_{mf or 'unknown'}"


def _facet_instrument_weight(facet: str, ick: str) -> float:
    """Wie stark ein Facet fuer diese Instrumentenklasse zaehlt (0..1)."""
    if facet in ("macro", "benchmark_correlation", "exchange_status"):
        if ick.startswith("btc_"):
            return 1.0
        if ick.startswith("eth_"):
            return 0.92
        if "spot" in ick:
            return 0.72
        return 0.85
    if facet in ("listing", "delisting"):
        if "spot" in ick or "margin" in ick:
            return 1.0
        return 0.78
    if facet == "funding_settlement":
        return 1.0 if "futures" in ick else 0.35
    if facet == "delivery":
        return 1.0 if "futures" in ick else 0.25
    if facet == "session_open":
        return 0.95
    return 0.8


def assess_structured_market_context(
    *,
    news_row: Mapping[str, Any] | None,
    symbol: str,
    market_family: str,
    proposed_direction: str,
    analysis_ts_ms: int,
    structure_events: list[Mapping[str, Any]] | None,
    primary_feature: Mapping[str, Any] | None,
    settings: Any,
) -> dict[str, Any]:
    """
    Liefert Audit-JSON inkl. Facets, Decay, Surprise, Konflikt-Codes, Live- und Reject-Hints.
    """
    if not bool(getattr(settings, "structured_market_context_enabled", True)):
        return {
            "version": STRUCTURED_MARKET_CONTEXT_VERSION,
            "disabled": True,
            "annotation_only_reasons_json": ["structured_market_context_disabled"],
            "live_execution_block_reasons_json": [],
            "deterministic_rejection_soft_json": [],
            "deterministic_rejection_hard_json": [],
            "composite_effective_factor_0_1": 1.0,
        }

    half_life_min = float(getattr(settings, "smc_news_decay_half_life_minutes", 120.0))
    half_life_min = max(5.0, half_life_min)
    thr_surprise_dir = float(getattr(settings, "smc_surprise_directional_threshold_0_1", 0.58))
    thr_live = float(getattr(settings, "smc_surprise_live_throttle_threshold_0_1", 0.52))
    shrink_floor = float(getattr(settings, "smc_composite_shrink_min_0_1", 0.88))
    shrink_floor = max(0.5, min(1.0, shrink_floor))
    hard_veto = bool(getattr(settings, "smc_hard_event_veto_enabled", False))
    thr_hard = float(getattr(settings, "smc_hard_event_veto_surprise_0_1", 0.82))

    text = _norm_text(news_row)
    facets = _detect_facets(text)
    if bool(getattr(settings, "smc_enable_structural_break_boost", True)) and _structure_break_hint(
        structure_events
    ):
        facets.append("structure_break")

    raw_tags: list[str] = []
    if news_row:
        raw = news_row.get("raw_json")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = None
        if isinstance(raw, dict) and isinstance(raw.get("topic_tags"), list):
            raw_tags = [str(x).strip().lower() for x in raw["topic_tags"] if str(x).strip()]
    for t in raw_tags:
        if t in ("macro", "regulatory", "security_incident", "listing"):
            if t == "macro" and "macro" not in facets:
                facets.append("macro")
            if t == "regulatory" and "exchange_status" not in facets:
                facets.append("macro")
            if t == "security_incident":
                facets.append("exchange_status")
            if t == "listing" and "listing" not in facets:
                facets.append("listing")

    ick = _instrument_context_key(symbol, market_family)
    weighted_facet_score = 0.0
    for f in set(facets):
        weighted_facet_score += _facet_instrument_weight(f, ick)
    facet_density_0_1 = min(1.0, weighted_facet_score / 6.0) if facets else 0.0

    rel = _f(news_row.get("relevance_score")) if news_row else None
    rel_0_1 = max(0.0, min(1.0, (rel or 0.0) / 100.0))
    pub = _published_ts_ms(news_row)
    age_min = 0.0
    decay = 1.0
    if pub is not None and analysis_ts_ms >= pub:
        age_min = max(0.0, (analysis_ts_ms - pub) / 60_000.0)
        decay = 0.5 ** (age_min / half_life_min)
    impact_w = str(news_row.get("impact_window") or "unknown") if news_row else "unknown"
    immediate = _impact_immediate(impact_w)
    window_boost = 1.22 if immediate else 1.0

    sent = _sentiment_0_1(news_row)
    sent_abs = abs(sent) if sent is not None else 0.0

    surprise = rel_0_1 * decay * sent_abs * window_boost * (0.55 + 0.45 * facet_density_0_1)
    surprise = max(0.0, min(1.0, float(surprise)))

    annotation_only: list[str] = []
    if not news_row:
        annotation_only.append("no_news_row_context")
    if facets and not news_row:
        pass

    conflict_codes: list[str] = []
    soft_reject: list[str] = []
    hard_reject: list[str] = []
    live_extra: list[str] = []
    d = proposed_direction.strip().lower()

    if news_row and d in ("long", "short") and sent is not None and surprise >= thr_surprise_dir:
        if sent < -0.25 and d == "long":
            conflict_codes.append("context_event_bearish_vs_long")
            soft_reject.append("context_technical_vs_event_long")
        if sent > 0.25 and d == "short":
            conflict_codes.append("context_event_bullish_vs_short")
            soft_reject.append("context_technical_vs_event_short")

    if "listing" in facets or "delisting" in facets:
        annotation_only.append("context_listing_delisting_annotation")
        if rel_0_1 >= 0.55 and surprise >= 0.35:
            soft_reject.append("context_listing_event_overlap")

    if "macro" in facets and immediate and rel_0_1 >= 0.5:
        soft_reject.append("context_macro_immediate_session_overlap")

    if "funding_settlement" in facets and isinstance(primary_feature, dict):
        fr = _f(primary_feature.get("funding_rate_bps"))
        if fr is not None and d == "long" and fr > 12 and surprise >= 0.4:
            conflict_codes.append("context_funding_adverse_with_event_narrative")
            soft_reject.append("context_funding_event_friction")
        if fr is not None and d == "short" and fr < -12 and surprise >= 0.4:
            conflict_codes.append("context_funding_adverse_with_event_narrative_short")
            soft_reject.append("context_funding_event_friction_short")

    if surprise >= thr_live and rel_0_1 >= 0.42:
        live_extra.append("context_live_event_surprise_escalation")

    if hard_veto and immediate and rel_0_1 >= 0.72 and surprise >= thr_hard and d in ("long", "short"):
        if sent is not None and sent < -0.4 and d == "long":
            hard_reject.append("context_hard_event_veto_long")
        if sent is not None and sent > 0.4 and d == "short":
            hard_reject.append("context_hard_event_veto_short")

    shrink = 1.0
    if soft_reject:
        n = min(4, len(soft_reject))
        shrink = max(shrink_floor, 1.0 - 0.035 * n)
    if "structure_break" in facets and conflict_codes:
        shrink = max(shrink_floor, shrink * 0.96)

    return {
        "version": STRUCTURED_MARKET_CONTEXT_VERSION,
        "instrument_context_key": ick,
        "facets_active_json": sorted(set(facets)),
        "facet_density_0_1": round(facet_density_0_1, 6),
        "relevance_score_raw": rel,
        "relevance_decayed_0_1": round(rel_0_1 * decay, 6),
        "news_age_minutes": round(age_min, 4),
        "decay_factor_0_1": round(decay, 6),
        "impact_window": impact_w,
        "impact_immediate": immediate,
        "sentiment_coarse_0_1": sent,
        "surprise_score_0_1": round(surprise, 6),
        "conflict_codes_json": conflict_codes,
        "annotation_only_reasons_json": annotation_only,
        "deterministic_rejection_soft_json": soft_reject,
        "deterministic_rejection_hard_json": hard_reject,
        "live_execution_block_reasons_json": live_extra,
        "composite_effective_factor_0_1": round(shrink, 6),
        "policy_note_de": (
            "annotation_only_reasons_json sind rein informativ. "
            "deterministic_rejection_* und composite_effective_factor wirken auf die deterministische Pipeline; "
            "live_execution_block_reasons_json wird im Live-Pfad mit Risk-Governor zusammengefuehrt."
        ),
    }


def refine_structured_market_context_for_playbook(
    base: Mapping[str, Any],
    *,
    playbook_family: str,
    settings: Any,
) -> dict[str, Any]:
    """Nach Playbook-Auswahl: Surprise neu skalieren, zusaetzliche Live-Blocker fuer news_shock-Pfade."""
    out = dict(base)
    if base.get("disabled"):
        return out
    fam = str(playbook_family or "").strip().lower()
    mult = 1.0
    if fam in ("news_shock", "time_window_effect"):
        mult = float(getattr(settings, "smc_playbook_news_sensitive_surprise_mult", 1.1))
    elif fam in ("trend_continuation", "trend"):
        mult = float(getattr(settings, "smc_playbook_trend_surprise_mult", 0.96))
    mult = max(0.5, min(1.35, mult))
    surprise = float(out.get("surprise_score_0_1") or 0.0) * mult
    surprise = max(0.0, min(1.0, surprise))
    out["surprise_score_playbook_adjusted_0_1"] = round(surprise, 6)
    out["playbook_overlay"] = {"playbook_family": fam or None, "surprise_multiplier": mult}

    thr_live = float(getattr(settings, "smc_surprise_live_throttle_threshold_0_1", 0.52))
    live = list(out.get("live_execution_block_reasons_json") or [])
    if fam == "news_shock" and surprise >= thr_live:
        tag = "context_playbook_news_shock_live_escalation"
        if tag not in live:
            live.append(tag)
    out["live_execution_block_reasons_json"] = live
    return out


def merge_live_reasons_into_risk_governor(risk_governor: dict[str, Any], smc: Mapping[str, Any]) -> None:
    """Mutiert risk_governor: haengt strukturierte Live-Gruende an live_execution_block_reasons_json an."""
    extra = smc.get("live_execution_block_reasons_json") or []
    if not isinstance(extra, list) or not extra:
        return
    cur = list(risk_governor.get("live_execution_block_reasons_json") or [])
    for tag in extra:
        if isinstance(tag, str) and tag.strip() and tag not in cur:
            cur.append(tag.strip())
    risk_governor["live_execution_block_reasons_json"] = cur
