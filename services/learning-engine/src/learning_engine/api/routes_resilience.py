from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.stress_test.adversarial_stress_pipeline import (
    resilience_to_dashboard_dict,
    run_adversarial_stress_suite,
)
from shared_py.service_auth import assert_internal_service_auth


def build_resilience_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning", "resilience"])

    @r.get("/learning/metrics/resilience-score")
    def resilience_score(
        attacks: int | None = None,
        x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
    ) -> dict[str, Any]:
        """
        Fuehrt (Teil-)Stress gegen AMS aus und liefert Dashboard-JSON
        (``resilience_score.schema.json``).
        """
        assert_internal_service_auth(settings, x_internal_service_key)
        n = int(attacks or settings.adversarial_stress_attack_count)
        if n < 50 or n > 10_000:
            raise HTTPException(status_code=400, detail="attacks 50..10000")
        try:
            result = run_adversarial_stress_suite(settings, attack_count=n)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)[:1200]) from exc
        return resilience_to_dashboard_dict(result)

    return r
