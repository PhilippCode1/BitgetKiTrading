"""Read-only Research-Benchmark-Evidence (keine Strategie-Mutation)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from learning_engine.config import LearningEngineSettings
from learning_engine.research.harness import (
    build_benchmark_evidence_report,
    report_to_markdown,
)
from learning_engine.storage.connection import db_connect
from learning_engine.storage.repo_backtest import (
    fetch_trade_evaluations_benchmark_sample,
)
from learning_engine.storage.repo_e2e import fetch_e2e_records_benchmark_sample


def _require_research_read_secret(
    settings: LearningEngineSettings,
    x_research_benchmark_secret: Annotated[str | None, Header()] = None,
) -> None:
    expected = (settings.research_benchmark_read_secret or "").strip()
    if not expected:
        return
    got = (x_research_benchmark_secret or "").strip()
    if got != expected:
        raise HTTPException(
            status_code=403,
            detail=(
                "research benchmark forbidden — "
                "X-Research-Benchmark-Secret erforderlich"
            ),
        )


def _clamp_limit(v: int | None, default: int) -> int:
    if v is None:
        return default
    return max(1, min(int(v), 50_000))


def build_research_benchmark_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "research"])

    @r.get("/learning/research/benchmark-evidence", response_model=None)
    def benchmark_evidence(
        symbol: str | None = None,
        limit_evaluations: int | None = None,
        limit_e2e: int | None = None,
        response_format: Annotated[str, Query(alias="format")] = "json",
        x_research_benchmark_secret: Annotated[str | None, Header()] = None,
    ) -> Response:
        """
        Aggregierte Metriken vs. heuristische Baselines;
        Counterfactual-Spezimen aus E2E.
        Kein Schreiben, keine Registry-/Risk-Aenderung.
        """
        _require_research_read_secret(settings, x_research_benchmark_secret)
        lim_ev = _clamp_limit(
            limit_evaluations,
            settings.research_benchmark_default_eval_limit,
        )
        lim_e2 = _clamp_limit(limit_e2e, settings.research_benchmark_default_e2e_limit)
        sym = symbol.strip().upper() if symbol and symbol.strip() else None
        fmt = (response_format or "json").strip().lower()
        if fmt not in ("json", "markdown"):
            raise HTTPException(
                status_code=400,
                detail="format muss json oder markdown sein",
            )

        with db_connect(settings.database_url) as conn:
            ev_rows = fetch_trade_evaluations_benchmark_sample(
                conn, symbol=sym, limit=lim_ev
            )
            e2e_rows = fetch_e2e_records_benchmark_sample(
                conn, symbol=sym, limit=lim_e2
            )

        report = build_benchmark_evidence_report(
            evaluation_rows=ev_rows,
            e2e_rows=e2e_rows,
            symbol_filter=sym,
            limit_evaluations=lim_ev,
            limit_e2e=lim_e2,
        )
        if fmt == "markdown":
            return Response(
                content=report_to_markdown(report),
                media_type="text/markdown; charset=utf-8",
            )
        return JSONResponse(content=report)

    return r
