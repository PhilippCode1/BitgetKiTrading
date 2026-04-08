from __future__ import annotations

from fastapi import APIRouter


def build_health_router(runtime) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health() -> dict:
        return runtime.health_payload()

    @router.get("/ready")
    def ready() -> dict:
        return runtime.ready_payload()

    return router
