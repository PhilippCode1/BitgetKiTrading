"""Atomarer Commit ins Apex-Audit-Ledger vor Freigabe der War-Room-Antwort."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from llm_orchestrator.config import LLMOrchestratorSettings
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

logger = logging.getLogger("llm_orchestrator.audit_ledger")


async def commit_war_room_to_audit_ledger(
    settings: LLMOrchestratorSettings,
    *,
    market_event_json: dict[str, Any],
    war_room: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Ruft audit-ledger auf. Bei konfigurierter Basis-URL wird die Antwort um ``apex_audit_ledger``
    erweitert; bei ``AUDIT_LEDGER_COMMIT_REQUIRED`` schlaegt ein Fehler hart fehl (kein Signal).
    """
    base = (settings.audit_ledger_base_url or "").strip().rstrip("/")
    if not base:
        if settings.audit_ledger_commit_required:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIT_LEDGER_UNAVAILABLE",
                    "message": "AUDIT_LEDGER_COMMIT_REQUIRED, aber AUDIT_LEDGER_BASE_URL fehlt.",
                },
            )
        return None
    key = (settings.service_internal_api_key or "").strip()
    if not key:
        if settings.audit_ledger_commit_required:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIT_LEDGER_AUTH_MISSING",
                    "message": "INTERNAL_API_KEY fehlt fuer audit-ledger Commit.",
                },
            )
        return None
    url = f"{base}/internal/v1/commit-war-room"
    headers = {INTERNAL_SERVICE_HEADER: key}
    payload = {"market_event_json": market_event_json, "war_room": war_room}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json=payload, headers=headers)
    except Exception as exc:
        logger.exception("audit-ledger HTTP-Fehler")
        if settings.audit_ledger_commit_required:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIT_LEDGER_COMMIT_FAILED",
                    "message": str(exc)[:800],
                },
            ) from exc
        return None
    if r.status_code >= 400:
        logger.warning(
            "audit-ledger commit status=%s body=%s", r.status_code, r.text[:500]
        )
        if settings.audit_ledger_commit_required:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIT_LEDGER_COMMIT_REJECTED",
                    "message": r.text[:1200],
                    "upstream_status": r.status_code,
                },
            )
        return None
    data = r.json()
    block = data.get("apex_audit_ledger")
    if not isinstance(block, dict):
        if settings.audit_ledger_commit_required:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIT_LEDGER_BAD_RESPONSE",
                    "message": "apex_audit_ledger fehlt in der Ledger-Antwort.",
                },
            )
        return None
    return block
