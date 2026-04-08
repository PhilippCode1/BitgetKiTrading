from __future__ import annotations

import re

import psycopg
from fastapi import APIRouter, HTTPException, Query

from signal_engine.config import normalize_timeframe
from signal_engine.schemas import ErrorResponse, SignalListResponse, SignalSingleResponse
from signal_engine.storage.repo import SignalRepository

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def build_signals_router(*, repo: SignalRepository) -> APIRouter:
    r = APIRouter(prefix="/signals", tags=["signals"])

    @r.get(
        "/latest",
        response_model=SignalSingleResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def latest(
        symbol: str = Query(..., min_length=1),
        timeframe: str = Query(..., min_length=1),
    ) -> dict[str, object]:
        tf = normalize_timeframe(timeframe)
        try:
            row = repo.get_latest_signal(symbol=symbol, timeframe=tf)
        except psycopg.Error:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": "Datenbank voruebergehend nicht erreichbar"},
            ) from None
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Kein Signal gefunden"},
            )
        return {"status": "ok", "signal": row}

    @r.get(
        "/recent",
        response_model=SignalListResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def recent(
        symbol: str = Query(..., min_length=1),
        timeframe: str = Query(..., min_length=1),
        limit: int = Query(default=50, ge=1, le=200),
        include_explain_md: bool = Query(
            default=False,
            description="Wenn false, werden explain_long_md/explain_long_json weggelassen.",
        ),
    ) -> dict[str, object]:
        tf = normalize_timeframe(timeframe)
        try:
            rows = repo.get_recent_signals(symbol=symbol, timeframe=tf, limit=limit)
        except psycopg.Error:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": "Datenbank voruebergehend nicht erreichbar"},
            ) from None
        if not include_explain_md:
            for srow in rows:
                srow.pop("explain_long_md", None)
                srow.pop("explain_long", None)
                srow.pop("explain_long_json", None)
        return {"status": "ok", "symbol": symbol, "timeframe": tf, "signals": rows}

    @r.get(
        "/by-id/{signal_id}",
        response_model=SignalSingleResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def by_id(signal_id: str) -> dict[str, object]:
        if not _UUID_RE.match(signal_id.strip()):
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Ungueltige signal_id"},
            )
        try:
            row = repo.get_signal_by_id(signal_id.strip())
        except psycopg.Error:
            raise HTTPException(
                status_code=503,
                detail={"status": "error", "message": "Datenbank voruebergehend nicht erreichbar"},
            ) from None
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Signal nicht gefunden"},
            )
        return {"status": "ok", "signal": row}

    return r
