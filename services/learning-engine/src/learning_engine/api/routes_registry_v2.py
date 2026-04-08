from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2 import service as registry_v2_service
from learning_engine.storage.connection import db_connect


class AssignSlotBody(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=128)
    run_id: UUID
    notes: str | None = Field(default=None, max_length=2000)
    changed_by: str = Field(default="api", min_length=1, max_length=128)
    promotion_manual_override: bool = False
    promotion_override_reason: str | None = Field(default=None, max_length=2000)
    scope_type: str = Field(
        default="global",
        max_length=32,
        description="global | market_family | market_cluster | market_regime | playbook | router_slot | symbol",
    )
    scope_key: str = Field(default="", max_length=256)


class MarkStableCheckpointBody(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=128)
    run_id: UUID | None = Field(
        default=None,
        description="Optional; Standard: aktueller Champion fuer scope",
    )
    marked_by: str = Field(..., min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)
    scope_type: str = Field(default="global", max_length=32)
    scope_key: str = Field(default="", max_length=256)


class RollbackStableBody(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=128)
    changed_by: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=8, max_length=2000)
    scope_type: str = Field(default="global", max_length=32)
    scope_key: str = Field(default="", max_length=256)


def _require_registry_mutation_secret(
    settings: LearningEngineSettings,
    x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Wenn MODEL_REGISTRY_MUTATION_SECRET gesetzt: nur kontrollierte Aufrufer (kein Telegram/öffentliches UI)."""
    expected = (settings.model_registry_mutation_secret or "").strip()
    if not expected:
        return
    got = (x_model_registry_mutation_secret or "").strip()
    if got != expected:
        raise HTTPException(
            status_code=403,
            detail="registry mutation forbidden — X-Model-Registry-Mutation-Secret erforderlich",
        )


def build_registry_v2_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "model-registry-v2"])

    @r.get("/learning/registry/v2/slots")
    def list_slots() -> dict[str, Any]:
        with db_connect(settings.database_url) as conn:
            return registry_v2_service.list_registry_snapshot(conn)

    @r.post("/learning/registry/v2/champion")
    def set_champion(
        body: AssignSlotBody,
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.assign_champion(
                    conn,
                    settings,
                    model_name=body.model_name.strip(),
                    run_id=body.run_id,
                    notes=body.notes,
                    changed_by=body.changed_by.strip(),
                    promotion_manual_override=body.promotion_manual_override,
                    promotion_override_reason=body.promotion_override_reason,
                    scope_type=body.scope_type.strip(),
                    scope_key=body.scope_key.strip(),
                )

    @r.post("/learning/registry/v2/challenger")
    def set_challenger(
        body: AssignSlotBody,
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.assign_challenger(
                    conn,
                    settings,
                    model_name=body.model_name.strip(),
                    run_id=body.run_id,
                    notes=body.notes,
                    changed_by=body.changed_by.strip(),
                    scope_type=body.scope_type.strip(),
                    scope_key=body.scope_key.strip(),
                )

    @r.delete("/learning/registry/v2/champion")
    def clear_champion(
        model_name: str,
        changed_by: str = "api",
        scope_type: str = "global",
        scope_key: str = "",
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.clear_registry_slot(
                    conn,
                    model_name=model_name.strip(),
                    role="champion",
                    changed_by=changed_by.strip() or "api",
                    scope_type=scope_type.strip(),
                    scope_key=scope_key.strip(),
                )

    @r.delete("/learning/registry/v2/challenger")
    def clear_challenger(
        model_name: str,
        changed_by: str = "api",
        scope_type: str = "global",
        scope_key: str = "",
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.clear_registry_slot(
                    conn,
                    model_name=model_name.strip(),
                    role="challenger",
                    changed_by=changed_by.strip() or "api",
                    scope_type=scope_type.strip(),
                    scope_key=scope_key.strip(),
                )

    @r.post("/learning/registry/v2/stable-checkpoint")
    def mark_stable_checkpoint(
        body: MarkStableCheckpointBody,
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.mark_stable_champion_checkpoint(
                    conn,
                    model_name=body.model_name.strip(),
                    run_id=body.run_id,
                    marked_by=body.marked_by.strip(),
                    notes=body.notes,
                    scope_type=body.scope_type.strip(),
                    scope_key=body.scope_key.strip(),
                )

    @r.post("/learning/registry/v2/rollback-stable")
    def rollback_stable(
        body: RollbackStableBody,
        x_model_registry_mutation_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_registry_mutation_secret(settings, x_model_registry_mutation_secret)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                return registry_v2_service.rollback_champion_to_stable_checkpoint(
                    conn,
                    settings,
                    model_name=body.model_name.strip(),
                    changed_by=body.changed_by.strip(),
                    reason=body.reason.strip(),
                    scope_type=body.scope_type.strip(),
                    scope_key=body.scope_key.strip(),
                )

    return r
