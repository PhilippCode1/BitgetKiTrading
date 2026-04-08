from __future__ import annotations

import re

import psycopg
from fastapi import APIRouter, HTTPException

from signal_engine.schemas import ErrorResponse, SignalExplainResponse
from signal_engine.storage.explanations_repo import ExplanationRepository
from signal_engine.storage.repo import SignalRepository

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def build_explain_router(
    *,
    repo: SignalRepository,
    explain_repo: ExplanationRepository,
) -> APIRouter:
    r = APIRouter(prefix="/signals", tags=["signals"])

    @r.get(
        "/by-id/{signal_id}/explain",
        response_model=SignalExplainResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    @r.get(
        "/{signal_id}/explain",
        response_model=SignalExplainResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def explain(signal_id: str) -> dict[str, object]:
        sid = signal_id.strip()
        if not _UUID_RE.match(sid):
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Ungueltige signal_id"},
            )
        try:
            sig = repo.get_signal_by_id(sid)
        except psycopg.Error:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": "Datenbank voruebergehend nicht erreichbar"},
            ) from None
        if sig is None:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Signal nicht gefunden"},
            )
        try:
            exp = explain_repo.fetch_by_signal_id(sid)
        except psycopg.Error:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": "Datenbank voruebergehend nicht erreichbar"},
            ) from None
        if exp is None:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Keine Erklaerung fuer dieses Signal"},
            )
        long_json = exp["explain_long_json"]
        sections = long_json.get("sections", {})
        risk = exp.get("risk_warnings_json") or []
        return {
            "status": "ok",
            "signal_id": sid,
            "symbol": sig.get("symbol"),
            "timeframe": sig.get("timeframe"),
            "explain_version": exp["explain_version"],
            "explain_short": exp["explain_short"],
            "explain_long_md": exp["explain_long_md"],
            "explain_long_json": long_json,
            "sections": sections,
            "risk_warnings": risk,
            "stop_explain": exp["stop_explain_json"],
            "targets_explain": exp["targets_explain_json"],
        }

    return r
