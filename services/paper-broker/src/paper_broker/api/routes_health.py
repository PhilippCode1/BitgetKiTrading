from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from paper_broker.storage.connection import paper_connect
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    merge_ready_details,
)


def _instrument_metadata_ready_tuple(
    runtime: Any,
    *,
    allow_degraded: bool,
) -> tuple[bool, str]:
    st = str(runtime.metadata_service.health_payload().get("status") or "unavailable")
    if runtime.catalog_block_reason is not None:
        return False, str(runtime.catalog_block_reason)
    if st == "ok":
        return True, st
    if allow_degraded and st == "degraded":
        return True, st
    return False, st


def build_health_router(runtime: Any) -> APIRouter:
    r = APIRouter()
    settings = runtime.settings
    bus = runtime.bus

    @r.get("/health")
    def health() -> dict[str, Any]:
        db_ok = False
        try:
            with paper_connect(settings.database_url, autocommit=True) as conn:
                conn.execute("SELECT 1")
            db_ok = True
        except Exception:
            pass
        redis_ok = False
        try:
            redis_ok = bool(bus.ping())
        except Exception:
            pass
        return {
            "status": (
                "ok"
                if db_ok and redis_ok and runtime.metadata_service.health_payload().get("status") == "ok"
                else "degraded"
            ),
            "service": "paper-broker",
            "port": settings.paper_broker_port,
            "database_ok": db_ok,
            "redis_ok": redis_ok,
            "execution_mode": settings.execution_mode,
            "strategy_execution_mode": settings.strategy_execution_mode,
            "execution_runtime": settings.execution_runtime_snapshot(),
            "paper_path_active": settings.paper_path_active,
            "shadow_trade_enable": settings.shadow_trade_enable,
            "live_trade_enable": settings.live_trade_enable,
            "paper_sim_mode": settings.paper_sim_mode,
            "instrument_catalog": runtime.catalog.health_payload(),
            "instrument_metadata": runtime.metadata_service.health_payload(),
            "catalog_block_reason": runtime.catalog_block_reason,
        }

    @r.get("/ready")
    def ready() -> dict[str, Any]:
        try:
            eb_ok = bool(bus.ping())
            eb_detail = "ok"
        except Exception as exc:
            eb_ok = False
            eb_detail = str(exc)[:200]
        parts = {
            "postgres": check_postgres(settings.database_url),
            "redis": check_redis_url(settings.redis_url),
            "eventbus": (eb_ok, eb_detail),
            "instrument_catalog": (
                runtime.catalog_block_reason is None,
                runtime.catalog_block_reason or runtime.catalog.health_payload().get("status", "ok"),
            ),
            "instrument_metadata": _instrument_metadata_ready_tuple(
                runtime,
                allow_degraded=settings.paper_broker_ready_allow_metadata_degraded,
            ),
        }
        parts = append_peer_readiness_checks(
            parts,
            settings.readiness_require_urls_raw,
            timeout_sec=float(settings.readiness_peer_timeout_sec),
        )
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    return r
