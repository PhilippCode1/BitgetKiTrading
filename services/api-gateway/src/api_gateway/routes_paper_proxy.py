from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_dashboard_queries import (
    fetch_equity_series,
    fetch_paper_metrics_summary,
    fetch_paper_open_positions,
    fetch_paper_trades_recent,
)
from api_gateway.db_paper_mutations import resolve_primary_paper_account_id
from api_gateway.db_paper_reads import (
    fetch_paper_account_ledger_recent,
    fetch_paper_journal_recent,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope

logger = logging.getLogger("api_gateway.paper_proxy")

router = APIRouter(prefix="/v1/paper", tags=["paper"])


def _page_limit() -> int:
    try:
        return max(1, min(500, int(get_gateway_settings().dashboard_page_size)))
    except ValueError:
        return 50


@router.get("/positions/open", response_model=None)
def paper_positions_open(symbol: str | None = Query(None)) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            positions = fetch_paper_open_positions(conn, symbol=symbol)
        es = len(positions) == 0
        return merge_read_envelope(
            {"positions": positions},
            status="ok",
            message="Keine offenen Paper-Positionen." if es else None,
            empty_state=es,
            degradation_reason="no_open_positions" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("paper positions: %s", exc)
        return merge_read_envelope(
            {"positions": []},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("paper positions: %s", exc)
        return merge_read_envelope(
            {"positions": []},
            status="degraded",
            message="Positionen nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/trades/recent", response_model=None)
def paper_trades_recent(
    symbol: str | None = Query(None),
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else _page_limit()
    lim = max(1, min(500, lim))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            trades = fetch_paper_trades_recent(conn, symbol=symbol, limit=lim)
        es = len(trades) == 0
        return merge_read_envelope(
            {"trades": trades, "limit": lim},
            status="ok",
            message="Keine Paper-Trades im Fenster." if es else None,
            empty_state=es,
            degradation_reason="no_trades" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("paper trades: %s", exc)
        return merge_read_envelope(
            {"trades": [], "limit": lim},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("paper trades: %s", exc)
        return merge_read_envelope(
            {"trades": [], "limit": lim},
            status="degraded",
            message="Trades nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/metrics/summary", response_model=None)
def paper_metrics_summary() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            summary = fetch_paper_metrics_summary(conn)
            equity_curve = fetch_equity_series(conn, max_points=200)
            ledger_recent: list[dict[str, Any]] = []
            aid = resolve_primary_paper_account_id(conn)
            if aid is not None:
                try:
                    ledger_recent = fetch_paper_account_ledger_recent(
                        conn, account_id=aid, limit=12
                    )
                except Exception:
                    ledger_recent = []
        payload = {**summary, "equity_curve": equity_curve, "account_ledger_recent": ledger_recent}
        return merge_read_envelope(
            payload,
            status="ok",
            message=None,
            empty_state=False,
            degradation_reason=None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("paper metrics: %s", exc)
        return merge_read_envelope(
            {
                "account": None,
                "fees_total_usdt": 0.0,
                "funding_total_usdt": 0.0,
                "equity_curve": [],
                "account_ledger_recent": [],
            },
            status="degraded",
            message="Paper-Metriken nicht ladbar: Datenbank fehlt.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("paper metrics: %s", exc)
        return merge_read_envelope(
            {
                "account": None,
                "fees_total_usdt": 0.0,
                "funding_total_usdt": 0.0,
                "equity_curve": [],
                "account_ledger_recent": [],
            },
            status="degraded",
            message="Paper-Metriken voruebergehend nicht verfuegbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/ledger/recent", response_model=None)
def paper_ledger_recent(
    limit: Annotated[int | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else 25
    lim = max(1, min(100, lim))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            if account_id and account_id.strip():
                aid = UUID(account_id.strip())
            else:
                resolved = resolve_primary_paper_account_id(conn)
                if resolved is None:
                    return merge_read_envelope(
                        {"entries": [], "limit": lim},
                        status="ok",
                        message="Kein Paper-Konto.",
                        empty_state=True,
                        degradation_reason="no_paper_account",
                        next_step=None,
                    )
                aid = resolved
            entries = fetch_paper_account_ledger_recent(conn, account_id=aid, limit=lim)
        es = len(entries) == 0
        return merge_read_envelope(
            {"entries": entries, "limit": lim, "account_id": str(aid)},
            status="ok",
            message="Keine Ledger-Eintraege." if es else None,
            empty_state=es,
            degradation_reason="no_ledger_entries" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("paper ledger: %s", exc)
        return merge_read_envelope(
            {"entries": [], "limit": lim},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("paper ledger: %s", exc)
        return merge_read_envelope(
            {"entries": [], "limit": lim},
            status="degraded",
            message="Ledger nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/journal/recent", response_model=None)
def paper_journal_recent(
    limit: Annotated[int | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else 40
    lim = max(1, min(200, lim))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            if account_id and account_id.strip():
                aid = UUID(account_id.strip())
            else:
                resolved = resolve_primary_paper_account_id(conn)
                if resolved is None:
                    return merge_read_envelope(
                        {"events": [], "limit": lim},
                        status="ok",
                        message="Kein Paper-Konto.",
                        empty_state=True,
                        degradation_reason="no_paper_account",
                        next_step=None,
                    )
                aid = resolved
            events = fetch_paper_journal_recent(
                conn, account_id=aid, limit=lim, symbol=symbol
            )
        es = len(events) == 0
        return merge_read_envelope(
            {"events": events, "limit": lim, "account_id": str(aid)},
            status="ok",
            message="Keine Journal-Ereignisse im Fenster." if es else None,
            empty_state=es,
            degradation_reason="no_journal_events" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("paper journal: %s", exc)
        return merge_read_envelope(
            {"events": [], "limit": lim},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid account_id") from None
    except Exception as exc:
        logger.warning("paper journal: %s", exc)
        return merge_read_envelope(
            {"events": [], "limit": lim},
            status="degraded",
            message="Journal nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
