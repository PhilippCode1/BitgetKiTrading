from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_applied_migrations, get_db_health

router = APIRouter(tags=["db"])


@router.get("/db/health")
def db_health() -> dict[str, object]:
    enforced = get_gateway_settings().sensitive_auth_enforced()
    try:
        payload = get_db_health()
    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Database health check failed.",
                }
                if enforced
                else {
                    "status": "error",
                    "message": f"database health failed: {exc}",
                }
            ),
        ) from exc

    if payload["status"] != "ok":
        raise HTTPException(
            status_code=503,
            detail=(
                {"code": "SERVICE_UNAVAILABLE", "message": "Database not ready."}
                if enforced
                else payload
            ),
        )
    if enforced:
        return {"status": "ok"}
    return payload


@router.get("/db/schema")
def db_schema(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, object]:
    try:
        migrations = get_applied_migrations()
    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": f"schema lookup failed: {exc}",
            },
        ) from exc

    return {
        "status": "ok",
        "migration_count": len(migrations),
        "migrations": migrations,
    }
