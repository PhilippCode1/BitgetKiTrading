from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, HTTPException, status
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_dashboard_queries import (
    fetch_registry_strategy_mutation_state,
    fetch_signal_path_playbooks_unlinked,
    fetch_strategies_registry,
    fetch_strategy_detail,
    fetch_strategy_status_row,
    fetch_version_row_for_registry,
    registry_insert_strategy_version,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope

logger = logging.getLogger("api_gateway.registry_proxy")

router = APIRouter(prefix="/v1/registry", tags=["registry"])


class AddStrategyVersionBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    definition: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_profile: dict[str, Any] = Field(default_factory=dict)


class PatchStrategyVersionBody(BaseModel):
    """In-place-Mutation ungueltig; nur Contract / Fehlerspektrum."""

    definition: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    risk_profile: dict[str, Any] | None = None


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
            signal_path_playbooks = fetch_signal_path_playbooks_unlinked(
                conn, limit=lim
            )
        es = len(items) == 0 and len(signal_path_playbooks) == 0
        msg: str | None = None
        if len(items) == 0 and len(signal_path_playbooks) > 0:
            msg = (
                "Keine learn.strategies-Zeilen, Playbooks im Signalpfad sichtbar — "
                "Registry-Seed pruefen oder learn.strategies.name = playbook_id."
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


@router.post(
    "/strategies/{strategy_id}/versions",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
def registry_add_strategy_version(
    strategy_id: UUID, body: AddStrategyVersionBody
) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            exists = conn.execute(
                "SELECT 1 FROM learn.strategies WHERE strategy_id = %s",
                (str(strategy_id),),
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="strategy not found")
            with conn.transaction():
                row = registry_insert_strategy_version(
                    conn,
                    strategy_id=strategy_id,
                    version=body.version,
                    definition=body.definition,
                    parameters=body.parameters,
                    risk_profile=body.risk_profile,
                )
    except HTTPException:
        raise
    except DatabaseHealthError as exc:
        logger.warning("registry add version: %s", exc)
        raise HTTPException(
            status_code=503, detail="Datenbank ist nicht konfiguriert."
        ) from exc
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=409,
            detail="version existiert bereits fuer diese Strategie",
        ) from exc
    except Exception as exc:
        logger.warning("registry add version: %s", exc)
        raise HTTPException(
            status_code=500, detail="Strategieversion nicht anlegbar."
        ) from exc
    return {
        "status": "ok",
        "strategy_id": str(strategy_id),
        "strategy_version_id": row["strategy_version_id"],
        "version": row["version"],
        "configuration_hash": row.get("configuration_hash"),
        "created_ts": row["created_ts"].isoformat() if row.get("created_ts") else None,
    }


@router.patch(
    "/strategies/{strategy_id}/versions/{strategy_version_id}",
    response_model=None,
)
def registry_patch_strategy_version(
    strategy_id: UUID,
    strategy_version_id: UUID,
    _body: PatchStrategyVersionBody,
) -> Any:
    """In-place-PATCH abgelehnt; live_champion liefert 409."""
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            vrow = fetch_version_row_for_registry(
                conn, strategy_id=strategy_id, strategy_version_id=strategy_version_id
            )
            if vrow is None:
                raise HTTPException(
                    status_code=404, detail="strategy version not found"
                )
            m = fetch_registry_strategy_mutation_state(conn, strategy_id)
            if m is None:
                raise HTTPException(status_code=404, detail="strategy not found")
            st = m.get("current_status")
            if st == "live_champion":
                msg = (
                    "Immutable Version: live_champion-Strategie schreibgeschuetzt; "
                    "neue Version per POST /v1/registry/strategies/{id}/versions."
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "IMMUTABLE_LIVE_CHAMPION", "message": msg},
                )
    except HTTPException:
        raise
    except DatabaseHealthError as exc:
        logger.warning("registry patch version: %s", exc)
        raise HTTPException(
            status_code=503, detail="Datenbank ist nicht konfiguriert."
        ) from exc
    except Exception as exc:
        logger.warning("registry patch version: %s", exc)
        raise HTTPException(
            status_code=500, detail="Strategieversion nicht aenderbar."
        ) from exc
    m400 = (
        "Aenderung nur per neuer version_id: "
        "POST /v1/registry/strategies/{id}/versions"
    )
    raise HTTPException(
        status_code=400,
        detail={"code": "IN_PLACE_VERSION_MUTATION_DISABLED", "message": m400},
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
