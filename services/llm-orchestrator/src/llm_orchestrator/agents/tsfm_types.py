"""Pydantic-Modelle fuer ``tsfm_signal_candidate`` (Feature-Engine / Eventbus)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TsfmSignalCandidatePayloadV1(BaseModel):
    """Validerter Kern aus ``EventEnvelope.payload`` (schema ``tsfm_signal_candidate/v1``)."""

    model_config = ConfigDict(populate_by_name=True)

    schema_id: str = Field(
        default="tsfm_signal_candidate/v1",
        alias="schema",
        description="Payload-Schema-ID (``schema`` im JSON).",
    )
    source_ts_ms: int = Field(ge=0)
    context_len: int = Field(ge=16, le=8192)
    forecast_horizon: int = Field(ge=1, le=512)
    forecast_sha256: str = Field(min_length=16, max_length=128)
    forecast_preview: list[float] = Field(default_factory=list)
    prep_meta: dict[str, Any] = Field(default_factory=dict)
    confidence_0_1: float = Field(ge=0.0, le=1.0)
    patch_variance: float = Field(default=0.0, ge=0.0)
    patch_incr_std: float = Field(default=0.0, ge=0.0)
    model_id: str = Field(default="", max_length=256)

    @field_validator("forecast_preview", mode="before")
    @classmethod
    def _cap_preview(cls, v: object) -> list[float]:
        if not isinstance(v, list):
            return []
        out: list[float] = []
        for x in v[:32]:
            try:
                out.append(float(x))
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def from_envelope_payload(cls, raw: dict[str, Any] | None) -> TsfmSignalCandidatePayloadV1 | None:
        if not isinstance(raw, dict):
            return None
        if str(raw.get("schema") or "") != "tsfm_signal_candidate/v1":
            return None
        try:
            return cls.model_validate(raw)
        except Exception:
            return None


class TsfmSemanticSynthesis(BaseModel):
    """Deterministisch aus numerischem Patch abgeleitete MARL-Sicht."""

    narrative_de: str = Field(min_length=8, max_length=4000)
    directional_bias: Literal["long", "short", "neutral"]
    synthesis_confidence_0_1: float = Field(ge=0.0, le=1.0)
    mean_reversion_score_0_1: float = Field(default=0.0, ge=0.0, le=1.0)
    horizon_ticks: int = Field(ge=1, le=512)
