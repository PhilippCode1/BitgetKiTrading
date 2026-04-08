from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from signal_engine.schemas import HealthResponse


def build_health_router(
    *, health_payload_fn: Callable[[], dict[str, Any]]
) -> APIRouter:
    r = APIRouter(tags=["health"])

    @r.get("/health", response_model=HealthResponse)
    def health() -> dict[str, object]:
        return health_payload_fn()

    return r
