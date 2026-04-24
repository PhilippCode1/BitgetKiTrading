"""
Quality Feedback Trace: operator_explain-Antworten fuer Produktions-Ausrichtung.

Siehe: tools/production_ai_alignment_check.py, public.ai_evaluation_logs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from shared_py.observability.request_context import get_current_trace_ids

from llm_orchestrator.config import LLMOrchestratorSettings

_log = logging.getLogger("llm_orchestrator.quality_feedback")

_WARN_DE = re.compile(
    r"(warn(ung|en)?|risiko|gefahr|vorsicht|verlust|nachteil|"
    r"abwärt|bearish|toxisch|kritisch|stopp|stop-?loss|"
    r"ungünstig|bedenklich|zurückhaltend|vorsorglich)",
    re.IGNORECASE | re.UNICODE,
)


def detect_ai_warned_from_result(result: dict[str, Any] | None) -> bool:
    """Risiko-/Warnindikatoren in explanation_de und non_authoritative_note_de."""
    if not isinstance(result, dict):
        return False
    parts: list[str] = []
    for key in ("explanation_de", "non_authoritative_note_de"):
        t = result.get(key)
        if isinstance(t, str) and t.strip():
            parts.append(t)
    blob = "\n".join(parts)
    return bool(blob.strip()) and bool(_WARN_DE.search(blob))


def _compact_api_response(response: dict[str, Any]) -> dict[str, Any]:
    """Speichert API-Response ohne provenance (Groesse)."""
    out = {k: v for k, v in response.items() if k != "provenance"}
    try:
        raw = json.dumps(out, default=str)
    except (TypeError, ValueError):
        return {"_serialization_error": True, "ok": response.get("ok")}
    if len(raw) > 200_000:
        res = out.get("result")
        if isinstance(res, dict) and isinstance(res.get("explanation_de"), str):
            ex = res["explanation_de"]
            if len(ex) > 12_000:
                res = {
                    **res,
                    "explanation_de": ex[:12_000] + "…[truncated]",
                }
                out = {**out, "result": res}
    return out


def _insert_ai_evaluation_log(
    settings: LLMOrchestratorSettings,
    *,
    task_type: str,
    response: dict[str, Any],
    execution_id: UUID | None = None,
    source_signal_id: UUID | None = None,
) -> None:
    dsn = (settings.database_url or "").strip()
    if not dsn or not settings.llm_ai_evaluation_log_enabled:
        return
    result = response.get("result")
    if not isinstance(result, dict):
        result = {}
    ai_warned = detect_ai_warned_from_result(result)
    compact = _compact_api_response(response)
    ok = bool(response.get("ok"))
    raw_orch = response.get("orchestrator_status")
    orch_s: str | None = raw_orch if isinstance(raw_orch, str) else None
    prov = response.get("provider")
    mod = response.get("model")
    trace_id, corr_id = get_current_trace_ids()
    try:
        import psycopg
    except ImportError:
        _log.warning("psycopg fehlt — ai_evaluation_logs nicht geschrieben")
        return
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.ai_evaluation_logs (
                        execution_id, source_signal_id, task_type, orchestrator_status,
                        response_ok, provider, model, response_json, ai_warned,
                        request_trace_id, request_correlation_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
                    )
                    """,
                    (
                        str(execution_id) if execution_id is not None else None,
                        str(source_signal_id) if source_signal_id is not None else None,
                        task_type,
                        orch_s,
                        ok,
                        str(prov) if prov is not None else None,
                        str(mod) if mod is not None else None,
                        json.dumps(compact, default=str),
                        ai_warned,
                        trace_id,
                        corr_id,
                    ),
                )
            conn.commit()
    except Exception as exc:
        _log.warning(
            "ai_evaluation_logs insert fehlgeschlagen task=%s execution_id=%s: %s",
            task_type,
            execution_id,
            exc,
            exc_info=False,
        )


def persist_operator_explain_row(
    settings: LLMOrchestratorSettings,
    *,
    execution_id: UUID,
    response: dict[str, Any],
) -> None:
    """Best-effort INSERT; Fehler nur loggen."""
    _insert_ai_evaluation_log(
        settings,
        task_type="operator_explain",
        response=response,
        execution_id=execution_id,
        source_signal_id=None,
    )


def persist_strategy_signal_explain_row(
    settings: LLMOrchestratorSettings,
    *,
    response: dict[str, Any],
    execution_id: UUID | None = None,
    source_signal_id: UUID | None = None,
) -> None:
    """Trace fuer Attribution (min. execution_id oder source_signal_id)."""
    if execution_id is None and source_signal_id is None:
        return
    _insert_ai_evaluation_log(
        settings,
        task_type="strategy_signal_explain",
        response=response,
        execution_id=execution_id,
        source_signal_id=source_signal_id,
    )


def log_quality_trace_startup(
    logger: logging.Logger,
    settings: LLMOrchestratorSettings,
) -> None:
    dsn = (settings.database_url or "").strip()
    if dsn and settings.llm_ai_evaluation_log_enabled:
        logger.info(
            "quality feedback trace: operator_explain+execution_id -> "
            "public.ai_evaluation_logs (DATABASE_URL, LLM_AI_EVAL_LOG_ENABLED)"
        )
    else:
        logger.info(
            "quality feedback trace: aus — kein DATABASE_URL "
            "oder LLM_AI_EVAL_LOG_ENABLED=false"
        )
