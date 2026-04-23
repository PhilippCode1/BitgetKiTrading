"""Pydantic-Modelle fuer AMS-Stresstest-Ergebnisse (Promotion / Dashboard)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdversarialAttackOutcomeV1(BaseModel):
    """Ein einzelner AMS-Aufruf."""

    attack_index: int = Field(ge=0)
    toxicity_0_1: float = Field(ge=0.0, le=1.0)
    high_risk: bool
    deflected: bool
    trap_score: float | None = None


class AdversarialStressRunResultV1(BaseModel):
    """Ergebnis einer kompletten Stress-Serie (z. B. 1000 Angriffe)."""

    schema_version: str = Field(default="adversarial_stress_run_v1")
    attacks_total: int = Field(ge=0)
    attacks_high_risk: int = Field(ge=0)
    attacks_deflected: int = Field(ge=0)
    resilience_score_0_100: float = Field(ge=0.0, le=100.0)
    min_resilience_required_0_100: float = Field(default=90.0, ge=0.0, le=100.0)
    passed: bool = Field(description="True wenn resilience >= min_required")
    classifier_path: str | None = None
    adversarial_engine_base_url: str | None = None
    sample_outcomes: list[AdversarialAttackOutcomeV1] = Field(
        default_factory=list,
        description="Erste N Outcomes fuer Audit/Dashboard",
    )
    details: dict[str, Any] = Field(default_factory=dict)
