"""Diagnostische News-Zustände: Kern-Pipeline vs. LLM-Anreicherung (ohne Kernsystem zu blockieren)."""

from __future__ import annotations

from typing import Any, Mapping

HEADLINE_NEWS_HEALTHY = "news_healthy"
HEADLINE_NEWS_STALE = "news_stale"
HEADLINE_LLM_ENRICHMENT_DEGRADED = "llm_enrichment_degraded"
HEADLINE_NEWS_DISABLED = "news_disabled"
HEADLINE_NEWS_CORE_DEGRADED = "news_core_degraded"


def build_news_health_contract(
    *,
    settings: Any,
    database_ok: bool,
    redis_ok: bool,
    ingest_worker_stats: Mapping[str, Any],
    freshness_row: Mapping[str, Any] | None,
    orchestrator_probe: Mapping[str, Any],
    last_scoring_batch: Mapping[str, Any] | None,
    now_ms: int,
) -> dict[str, Any]:
    poll_ms = max(1, int(settings.news_poll_interval_sec)) * 1000
    stale_threshold_ms = max(
        int(settings.news_stale_warn_after_ms),
        3 * poll_ms,
    )
    orch_ok = bool(orchestrator_probe.get("reachable"))

    pipeline_on = bool(settings.news_pipeline_enabled)
    llm_on = bool(settings.news_llm_enabled)

    fr = freshness_row or {}
    max_ing = fr.get("max_ingested_ts_ms")
    max_scored = fr.get("max_scored_ts_ms")
    pending = int(fr.get("pending_scoring_count") or 0)
    total = int(fr.get("total_items") or 0)

    max_ing_i = int(max_ing) if max_ing is not None else None
    max_scored_i = int(max_scored) if max_scored is not None else None

    warnings_de: list[str] = []
    warnings_en: list[str] = []

    if not database_ok or not redis_ok:
        core = "error"
        headline = HEADLINE_NEWS_CORE_DEGRADED
        if not database_ok:
            warnings_de.append("Postgres nicht erreichbar — News-Pipeline gestoppt.")
            warnings_en.append("Postgres unreachable — news pipeline cannot persist.")
        if not redis_ok:
            warnings_de.append("Redis nicht erreichbar — Eventbus/Event-Publishing betroffen.")
            warnings_en.append("Redis unreachable — event bus affected.")
    elif not pipeline_on:
        core = "disabled"
        headline = HEADLINE_NEWS_DISABLED
        warnings_de.append(
            "News-Ingestion ist per NEWS_PIPELINE_ENABLED=false abgeschaltet — keine neuen Items."
        )
        warnings_en.append(
            "News ingest disabled via NEWS_PIPELINE_ENABLED=false — no new items."
        )
        if llm_on and not orch_ok:
            warnings_de.append(
                "LLM-Orchestrator derzeit nicht erreichbar (nur Diagnose; Ingestion ohnehin aus)."
            )
            warnings_en.append("Orchestrator unreachable (diagnostic; ingest already off).")
    elif total == 0:
        core = "idle_empty"
        headline = HEADLINE_NEWS_STALE
        warnings_de.append(
            "Noch keine News-Zeilen in app.news_items — Ingestion liefert noch keine Treffer oder DB ist leer."
        )
        warnings_en.append("No rows in app.news_items yet — ingest may be empty or filters strict.")
    elif max_ing_i is not None and (now_ms - max_ing_i) > stale_threshold_ms:
        core = "stale"
        headline = HEADLINE_NEWS_STALE
        age_m = (now_ms - max_ing_i) // 60_000
        warnings_de.append(
            f"Letzte Ingestion zu alt (~{age_m} min) — Schwelle {max(1, stale_threshold_ms // 60_000)} min (konfigurierbar)."
        )
        warnings_en.append(
            f"Latest ingest is old (~{age_m} min) vs threshold {max(1, stale_threshold_ms // 60_000)} min."
        )
    else:
        core = "healthy"
        headline = HEADLINE_NEWS_HEALTHY

    if not database_ok or not redis_ok:
        llm_state = "unknown"
    elif not llm_on:
        llm_state = "disabled"
        if headline == HEADLINE_NEWS_HEALTHY:
            warnings_de.append(
                "LLM-Anreicherung aus (NEWS_LLM_ENABLED=false) — nur regelbasiertes Scoring."
            )
            warnings_en.append("LLM enrichment off — rule-only scoring.")
    elif not orch_ok:
        llm_state = "degraded"
        detail = str(orchestrator_probe.get("detail") or "unreachable")
        warnings_de.append(
            f"LLM-Orchestrator nicht erreichbar ({detail[:120]}) — Scoring fällt auf Regeln zurück."
        )
        warnings_en.append(f"LLM orchestrator unreachable ({detail[:120]}) — rule-only scoring.")
        if headline == HEADLINE_NEWS_HEALTHY:
            headline = HEADLINE_LLM_ENRICHMENT_DEGRADED
    else:
        llm_state = "healthy"
        ls = last_scoring_batch or {}
        cand = int(ls.get("candidates") or 0)
        ok_c = int(ls.get("llm_enrich_ok") or 0)
        fail_c = int(ls.get("llm_enrich_fail") or 0)
        if cand >= 5 and fail_c >= 5 and ok_c == 0:
            llm_state = "degraded"
            warnings_de.append(
                "Letzte Scoring-Batches: LLM-Anreicherung schlägt wiederholt fehl (OpenAI/Circuit?)."
            )
            warnings_en.append("Recent scoring batches: LLM enrichment failing repeatedly.")
            if headline == HEADLINE_NEWS_HEALTHY:
                headline = HEADLINE_LLM_ENRICHMENT_DEGRADED

    if pending > 200 and core == "healthy":
        warnings_de.append(
            f"Hoher Rückstau unscored/pending ({pending}) — POST /score/now oder Cron prüfen."
        )
        warnings_en.append(f"Large pending scoring backlog ({pending}).")

    return {
        "contract_version": "1.0.0",
        "headline": headline,
        "core_pipeline": core,
        "llm_enrichment": llm_state,
        "llm_enrichment_config_enabled": llm_on,
        "news_pipeline_enabled": pipeline_on,
        "freshness": {
            "max_ingested_ts_ms": max_ing_i,
            "max_scored_ts_ms": max_scored_i,
            "pending_scoring_count": pending,
            "total_items": total,
            "stale_threshold_ms": stale_threshold_ms,
        },
        "orchestrator_probe": dict(orchestrator_probe),
        "last_scoring_batch": dict(last_scoring_batch) if last_scoring_batch else None,
        "ingest_worker_last_cycle": dict(ingest_worker_stats),
        "warnings_de": warnings_de,
        "warnings_en": warnings_en,
    }
