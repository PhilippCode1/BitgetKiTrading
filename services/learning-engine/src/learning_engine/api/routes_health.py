from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from learning_engine.config import LearningEngineSettings
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    merge_ready_details,
)


def build_health_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter()

    @r.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "learning-engine"}

    @r.get("/ready")
    def ready() -> dict[str, Any]:
        parts = {
            "postgres": check_postgres(settings.database_url),
            "redis": check_redis_url(settings.redis_url),
        }
        parts = append_peer_readiness_checks(
            parts,
            settings.readiness_require_urls_raw,
            timeout_sec=float(settings.readiness_peer_timeout_sec),
        )
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    return r
