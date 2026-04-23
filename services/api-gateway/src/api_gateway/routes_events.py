from __future__ import annotations

import json
import os
from typing import Any

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from redis import Redis
from redis.exceptions import RedisError
from shared_py.eventbus import EVENT_STREAMS
from shared_py.redis_client import get_or_create_sync_pooled_client

from api_gateway.config import get_gateway_settings

router = APIRouter(prefix="/events", tags=["events"])


def _redis() -> Redis:
    s = get_gateway_settings()
    redis_url = s.redis_url.strip() or (os.environ.get("REDIS_URL", "") or "").strip()
    if not redis_url:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "REDIS_URL fehlt",
            },
        )
    return get_or_create_sync_pooled_client(
        redis_url,
        role="gateway_events",
        decode_responses=True,
        max_connections=48,
    )


def _default_count() -> int:
    return int(os.environ.get("EVENTBUS_DEFAULT_COUNT", "10"))


@router.get("/health")
def events_health() -> dict[str, object]:
    enforced = get_gateway_settings().sensitive_auth_enforced()
    try:
        redis_client = _redis()
        ok = bool(redis_client.ping())
        if not ok:
            raise RedisError("ping failed")
        if enforced:
            return {"status": "ok"}
        return {
            "status": "ok",
            "ping": True,
            "streams": {stream: int(redis_client.xlen(stream)) for stream in EVENT_STREAMS},
        }
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Events-Backend nicht erreichbar.",
                }
                if enforced
                else {
                    "status": "error",
                    "message": f"events health failed: {exc}",
                }
            ),
        ) from exc


@router.get("/tail")
def tail_events(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
    stream: str = Query(...),
    count: int | None = Query(default=None, ge=1, le=200),
) -> dict[str, object]:
    if stream not in EVENT_STREAMS:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"ungueltiger Stream: {stream}",
            },
        )
    effective_count = count or _default_count()
    try:
        redis_client = _redis()
        items = redis_client.xrevrange(stream, max="+", min="-", count=effective_count)
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": f"events tail failed: {exc}",
            },
        ) from exc
    return {
        "status": "ok",
        "stream": stream,
        "count": len(items),
        "items": [_format_stream_item(item) for item in items],
    }


@router.get("/dlq")
def tail_dlq(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
    count: int | None = Query(default=None, ge=1, le=200),
) -> dict[str, object]:
    return tail_events(stream="events:dlq", count=count)


def _format_stream_item(item: tuple[str, dict[str, str]]) -> dict[str, Any]:
    message_id, fields = item
    raw_data = fields.get("data", "")
    parsed: dict[str, Any] | None = None
    if raw_data:
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = None
    return {
        "id": message_id,
        "data": parsed if parsed is not None else raw_data,
    }
