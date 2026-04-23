from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage.repo_tsfm_war_room_audit import insert_tsfm_war_room_audit
from shared_py.service_auth import assert_internal_service_auth


class TsfmWarRoomAuditIn(BaseModel):
    recorded_ts_ms: int = Field(ge=0)
    symbol: str = Field(min_length=3, max_length=64)
    forecast_sha256: str | None = Field(default=None, max_length=128)
    tsfm_direction: str | None = Field(default=None, max_length=16)
    tsfm_confidence_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    tsfm_horizon_ticks: int | None = Field(default=None, ge=1, le=4096)
    quant_action: str | None = Field(default=None, max_length=32)
    quant_confidence_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    quant_confidence_effective_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_action: str | None = Field(default=None, max_length=32)
    macro_news_shock: bool = False
    consensus_action: str | None = Field(default=None, max_length=32)
    consensus_status: str | None = Field(default=None, max_length=64)
    quant_weight_base: float | None = None
    quant_weight_effective: float | None = None
    shock_penalty_applied: bool = False
    anchor_price: float | None = None
    quant_foundation_path_ms: float | None = Field(default=None, ge=0.0, le=60_000.0)
    war_room_eval_wall_ms: float | None = Field(default=None, ge=0.0, le=600_000.0)
    outcome_return_pct: float | None = None
    outcome_eval_ts_ms: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def build_tsfm_war_room_audit_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "tsfm"])

    @r.post("/learning/tsfm-war-room-audit")
    def ingest_tsfm_war_room_audit(
        body: TsfmWarRoomAuditIn,
        x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
    ) -> dict[str, Any]:
        assert_internal_service_auth(settings, x_internal_service_key)
        row = {
            "recorded_ts_ms": body.recorded_ts_ms,
            "symbol": body.symbol.strip().upper(),
            "forecast_sha256": body.forecast_sha256,
            "tsfm_direction": body.tsfm_direction,
            "tsfm_confidence_0_1": body.tsfm_confidence_0_1,
            "tsfm_horizon_ticks": body.tsfm_horizon_ticks,
            "quant_action": body.quant_action,
            "quant_confidence_0_1": body.quant_confidence_0_1,
            "quant_confidence_effective_0_1": body.quant_confidence_effective_0_1,
            "macro_action": body.macro_action,
            "macro_news_shock": body.macro_news_shock,
            "consensus_action": body.consensus_action,
            "consensus_status": body.consensus_status,
            "quant_weight_base": body.quant_weight_base,
            "quant_weight_effective": body.quant_weight_effective,
            "shock_penalty_applied": body.shock_penalty_applied,
            "anchor_price": body.anchor_price,
            "quant_foundation_path_ms": body.quant_foundation_path_ms,
            "war_room_eval_wall_ms": body.war_room_eval_wall_ms,
            "outcome_return_pct": body.outcome_return_pct,
            "outcome_eval_ts_ms": body.outcome_eval_ts_ms,
            "payload": body.payload,
        }
        try:
            with db_connect(settings.database_url) as conn:
                aid = insert_tsfm_war_room_audit(conn, row)
                conn.commit()
        except Exception as exc:  # pragma: no cover — DB-Pfad
            raise HTTPException(status_code=500, detail=str(exc)[:800]) from exc
        return {"status": "ok", "audit_id": aid}

    return r
