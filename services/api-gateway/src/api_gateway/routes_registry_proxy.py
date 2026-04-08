from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_dashboard_queries import (
    fetch_signal_path_playbooks_unlinked,
    fetch_strategies_registry,
    fetch_strategy_detail,
    fetch_strategy_status_row,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope

logger = logging.getLogger("api_gateway.registry_proxy")

router = APIRouter(prefix="/v1/registry", tags=["registry"])


def _page_limit() -> int:
    try:
        return max(1, min(200, int(get_gateway_settings().dashboard_page_size)))
    except ValueError:
        return 50


@router.get("/strategies", response_model=None)
def registry_strategies() -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            lim = _page_limit()
            items = fetch_strategies_registry(conn, limit=lim)
            signal_path_playbooks = fetch_signal_path_playbooks_unlinked(conn, limit=lim)
        es = len(items) == 0 and len(signal_path_playbooks) == 0
        msg: str | None = None
        if len(items) == 0 and len(signal_path_playbooks) > 0:
            msg = (
                "Keine Zeilen in learn.strategies, aber Playbooks im Signalpfad sind sichtbar — "
                "Registry-Seed/Migration pruefen oder Namen angleichen (learn.strategies.name = playbook_id)."
            )
        elif len(items) == 0:
            msg = "Keine Strategien in der Registry."
        return merge_read_envelope(
            {"items": items, "signal_path_playbooks": signal_path_playbooks},
            status="ok",
            message=msg,
            empty_state=es,
            degradation_reason="no_strategies" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("registry strategies: %s", exc)
        return merge_read_envelope(
            {"items": [], "signal_path_playbooks": []},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("registry strategies: %s", exc)
        return merge_read_envelope(
            {"items": [], "signal_path_playbooks": []},
            status="degraded",
            message="Strategien nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/strategies/{strategy_id}/status", response_model=None)
def registry_strategy_status(strategy_id: UUID) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_strategy_status_row(conn, strategy_id)
    except DatabaseHealthError as exc:
        logger.warning("registry status: %s", exc)
        return merge_read_envelope(
            {"strategy_id": str(strategy_id)},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("registry status: %s", exc)
        return merge_read_envelope(
            {"strategy_id": str(strategy_id)},
            status="degraded",
            message="Status nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )


@router.get("/strategies/{strategy_id}", response_model=None)
def registry_strategy_detail(strategy_id: UUID) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_strategy_detail(conn, strategy_id)
    except DatabaseHealthError as exc:
        logger.warning("registry detail: %s", exc)
        return merge_read_envelope(
            {"strategy_id": str(strategy_id)},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("registry detail: %s", exc)
        return merge_read_envelope(
            {"strategy_id": str(strategy_id)},
            status="degraded",
            message="Strategie-Detail nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )
