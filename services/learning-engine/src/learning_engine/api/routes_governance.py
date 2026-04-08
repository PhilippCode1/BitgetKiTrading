from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from learning_engine.config import LearningEngineSettings
from learning_engine.curriculum.expert_curriculum import build_expert_curriculum_overlay
from learning_engine.storage import repo_learning_context
from learning_engine.storage.connection import db_connect
from learning_engine.training.specialist_readiness import (
    audit_specialist_training_readiness,
)


class ContextSignalBody(BaseModel):
    source_kind: str = Field(
        ...,
        min_length=2,
        max_length=64,
        description=(
            "shadow | paper | post_trade_review | operator_context | live_outcome"
        ),
    )
    reference_json: dict[str, Any] = Field(default_factory=dict)
    payload_redacted_json: dict[str, Any] = Field(default_factory=dict)
    policy_rewrite_forbidden: bool = True
    curriculum_version: str = Field(default="specialist-curriculum-v2", max_length=128)


def _require_context_ingest_secret(
    settings: LearningEngineSettings,
    x_learning_context_ingest_secret: Annotated[str | None, Header()] = None,
) -> None:
    expected = (settings.learning_context_ingest_secret or "").strip()
    if not expected:
        return
    got = (x_learning_context_ingest_secret or "").strip()
    if got != expected:
        raise HTTPException(
            status_code=403,
            detail=(
                "context ingest forbidden — "
                "X-Learning-Context-Ingest-Secret erforderlich"
            ),
        )


def build_governance_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "governance"])

    @r.get("/learning/governance/expert-curriculum")
    def expert_curriculum(symbol: str | None = None) -> dict[str, Any]:
        """Curriculum + Readiness (Familie, Cluster, Regime, Playbook, Symbol)."""
        with db_connect(settings.database_url) as conn:
            report = audit_specialist_training_readiness(conn, settings, symbol=symbol)
        overlay = build_expert_curriculum_overlay(report, settings)
        return {"status": "ok", "readiness": report, "curriculum": overlay}

    @r.post("/learning/governance/context-signals")
    def ingest_context_signal(
        body: ContextSignalBody,
        x_learning_context_ingest_secret: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Kontext aus Shadow/Paper/Review/Outcomes; Operator ohne Policy-Rewrite."""
        _require_context_ingest_secret(settings, x_learning_context_ingest_secret)
        try:
            with db_connect(settings.database_url) as conn:
                with conn.transaction():
                    eid = repo_learning_context.insert_learning_context_signal(
                        conn,
                        source_kind=body.source_kind.strip(),
                        reference_json=body.reference_json,
                        payload_redacted_json=body.payload_redacted_json,
                        policy_rewrite_forbidden=body.policy_rewrite_forbidden,
                        curriculum_version=body.curriculum_version.strip(),
                    )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "context_signal_id": str(eid)}

    @r.get("/learning/governance/context-signals/recent")
    def list_context_signals(limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit 1..200")
        with db_connect(settings.database_url) as conn:
            items = repo_learning_context.fetch_recent_context_signals(
                conn, limit=limit
            )
        return {"status": "ok", "items": items, "limit": limit}

    return r
