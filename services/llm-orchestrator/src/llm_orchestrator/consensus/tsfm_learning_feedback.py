"""Fire-and-forget: TimesFM/War-Room-Zeile an learning-engine (RL-Label-Vorstufe)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from llm_orchestrator.config import LLMOrchestratorSettings
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

logger = logging.getLogger("llm_orchestrator.consensus.tsfm_learning_feedback")


async def post_tsfm_war_room_audit(settings: LLMOrchestratorSettings, body: dict[str, Any]) -> None:
    base = str(getattr(settings, "learning_engine_base_url", "") or "").strip().rstrip("/")
    if not base:
        return
    url = f"{base}/learning/tsfm-war-room-audit"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if key:
        headers[INTERNAL_SERVICE_HEADER] = key
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(url, json=body, headers=headers)
            if r.status_code >= 400:
                logger.warning(
                    "tsfm-war-room-audit POST failed status=%s body=%s",
                    r.status_code,
                    (r.text or "")[:400],
                )
    except Exception as exc:  # pragma: no cover — Netzwerk optional
        logger.debug("tsfm-war-room-audit POST skipped: %s", exc)
