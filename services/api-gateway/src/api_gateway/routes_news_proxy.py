from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_dashboard_queries import fetch_news_by_id, fetch_news_scored
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope

logger = logging.getLogger("api_gateway.news_proxy")

router = APIRouter(prefix="/v1/news", tags=["news"])


def _page_limit() -> int:
    try:
        return max(1, min(200, int(get_gateway_settings().dashboard_page_size)))
    except ValueError:
        return 50


@router.get("/scored", response_model=None)
def news_scored(
    min_score: int = Query(0, ge=0, le=100),
    sentiment: str | None = Query(None),
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else _page_limit()
    lim = max(1, min(200, lim))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_news_scored(conn, min_score=min_score, sentiment=sentiment, limit=lim)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": lim},
            status="ok",
            message="Keine News im Score-Filter." if es else None,
            empty_state=es,
            degradation_reason="no_news" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("news scored: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": lim},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("news scored: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": lim},
            status="degraded",
            message="News nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/{news_id}", response_model=None)
def news_detail(news_id: UUID) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_news_by_id(conn, news_id)
    except DatabaseHealthError as exc:
        logger.warning("news detail: %s", exc)
        return merge_read_envelope(
            {"news_id": str(news_id)},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("news detail: %s", exc)
        return merge_read_envelope(
            {"news_id": str(news_id)},
            status="degraded",
            message="News-Artikel nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="news not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )
