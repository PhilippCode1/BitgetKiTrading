from __future__ import annotations

from typing import Any, Protocol, cast

from fastapi import APIRouter


class HealthRuntime(Protocol):
    def health_payload(self) -> dict[str, Any]: ...

    def ready_payload(self) -> dict[str, Any]: ...


def build_health_router(runtime: HealthRuntime) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health() -> dict[str, Any]:
        return cast(dict[str, Any], runtime.health_payload())

    @router.get("/ready")
    def ready() -> dict[str, Any]:
        return cast(dict[str, Any], runtime.ready_payload())

    return router
