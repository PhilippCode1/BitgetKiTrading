from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.registry import models, storage
from shared_py.eventbus import EventEnvelope, RedisStreamBus
from shared_py.eventbus.envelope import STREAM_STRATEGY_REGISTRY_UPDATED

logger = logging.getLogger("learning_engine.registry")


def _default_status(settings: LearningEngineSettings) -> str:
    return settings.strategy_registry_default_status


def publish_registry_snapshot(
    bus: RedisStreamBus,
    *,
    strategy_id: UUID,
    name: str,
    scope_json: dict[str, Any] | None,
    old_status: str | None,
    new_status: str,
    reason: str | None,
    promoted_names: list[str],
) -> None:
    stream = STREAM_STRATEGY_REGISTRY_UPDATED
    scope = models.StrategyScope.model_validate(scope_json or {})
    instrument = scope.instrument_identity()
    env = EventEnvelope(
        event_type="strategy_registry_updated",
        symbol=scope.symbol,
        instrument=instrument,
        payload={
            "strategy_id": str(strategy_id),
            "name": name,
            "scope": scope.model_dump(mode="json"),
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "promoted_strategy_names": promoted_names,
        },
        trace={"source": "learning_engine.registry"},
    )
    mid = bus.publish(stream, env)
    logger.info("strategy_registry event published id=%s", mid)


def create_strategy(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    body: models.CreateStrategyRequest,
) -> dict[str, Any]:
    init_st = _default_status(settings)
    try:
        row = storage.insert_strategy(
            conn,
            name=body.name,
            description=body.description,
            scope_json=body.scope.model_dump(mode="json"),
            initial_status=init_st,
        )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="strategy name bereits vergeben") from exc
    return row


def add_version(
    conn: psycopg.Connection[Any],
    strategy_id: UUID,
    body: models.AddVersionRequest,
) -> dict[str, Any]:
    strat = storage.fetch_strategy_by_id(conn, strategy_id)
    if strat is None:
        raise HTTPException(status_code=404, detail="strategy nicht gefunden")
    try:
        vrow = storage.insert_version(
            conn,
            strategy_id=strategy_id,
            version=body.version,
            definition_json=body.definition,
            parameters_json=body.parameters,
            risk_profile_json=body.risk_profile,
        )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="version existiert bereits") from exc
    return vrow


def set_status(
    conn: psycopg.Connection[Any],
    bus: RedisStreamBus,
    strategy_id: UUID,
    body: models.SetStatusRequest,
) -> dict[str, Any]:
    strat = storage.fetch_strategy_by_id(conn, strategy_id)
    if strat is None:
        raise HTTPException(status_code=404, detail="strategy nicht gefunden")
    old = storage.get_current_status(conn, strategy_id)
    if old is None:
        raise HTTPException(status_code=500, detail="strategy_status fehlt")
    new = body.new_status.value
    if old == new:
        raise HTTPException(status_code=400, detail="status unveraendert")
    if not models.transition_allowed(old, new):
        raise HTTPException(
            status_code=400,
            detail=f"uebergang {old!r} -> {new!r} nicht erlaubt",
        )
    if models.requires_promotion_manual_override(old, new) and not body.manual_override:
        raise HTTPException(
            status_code=400,
            detail="candidate -> promoted erfordert manual_override=true bis Prompt-23-Gates",
        )
    warnings: list[str] = []
    if models.requires_promotion_manual_override(old, new) and body.manual_override:
        warnings.append("manual_override: Promotion-Gates (Prompt 23) noch nicht aktiv")

    storage.update_status(
        conn,
        strategy_id=strategy_id,
        new_status=new,
        old_status=old,
        reason=body.reason,
        changed_by=body.changed_by,
    )
    promoted = storage.list_promoted_names(conn)
    publish_registry_snapshot(
        bus,
        strategy_id=strategy_id,
        name=str(strat["name"]),
        scope_json=strat.get("scope_json") if isinstance(strat, dict) else None,
        old_status=old,
        new_status=new,
        reason=body.reason,
        promoted_names=promoted,
    )
    return {"status": "ok", "current_status": new, "warnings": warnings}


def get_strategy_detail(conn: psycopg.Connection[Any], strategy_id: UUID) -> dict[str, Any]:
    row = storage.fetch_strategy_by_id(conn, strategy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="strategy nicht gefunden")
    versions = storage.list_versions(conn, strategy_id)
    return {"strategy": dict(row), "versions": versions}


def list_strategies(conn: psycopg.Connection[Any], status: str | None) -> list[dict[str, Any]]:
    if status and status not in ("promoted", "candidate", "shadow", "retired"):
        raise HTTPException(status_code=400, detail="ungueltiger status filter")
    return storage.list_strategies(conn, status=status)
