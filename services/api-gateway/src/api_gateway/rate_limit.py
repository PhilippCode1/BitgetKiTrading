"""Redis-basierte Rate-Limits (oeffentlich vs. sensibel vs. Admin-Mutation)."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Callable

from fastapi import Request, Response
from redis import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from api_gateway.config import get_gateway_settings
from api_gateway.errors import http_error_envelope

logger = logging.getLogger("api_gateway.rate_limit")

_rl_redis: Redis | None = None


def get_rate_limit_redis() -> Redis | None:
    global _rl_redis
    if _rl_redis is not None:
        return _rl_redis
    url = get_gateway_settings().redis_url.strip()
    if not url:
        return None
    _rl_redis = Redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return _rl_redis

SENSITIVE_PREFIXES: tuple[str, ...] = (
    "/v1/auth",
    "/v1/live",
    "/v1/live-broker",
    "/v1/learning",
    "/v1/backtests",
    "/v1/registry",
    "/v1/alerts",
    "/v1/monitor",
    "/v1/paper",
    "/v1/signals",
    "/v1/news",
    "/v1/llm",
    "/v1/commerce",
    "/events/tail",
    "/events/dlq",
    "/db/schema",
)


def _client_bucket_key(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.strip():
        h = hashlib.sha256(auth.strip().encode()).hexdigest()[:24]
        return f"a:{h}"
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd.strip():
        return f"f:{fwd.split(',')[0].strip()[:64]}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "ip:unknown"


def _is_safety_mutation(path: str, method: str) -> bool:
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return False
    if path.startswith("/v1/live-broker/safety/") and method == "POST":
        return True
    if (
        "/executions/" in path
        and path.rstrip("/").endswith("/operator-release")
        and method == "POST"
    ):
        return True
    return False


def _classify_path(path: str) -> str:
    if path.startswith("/v1/admin"):
        return "admin"
    if path.startswith("/events/tail") or path.startswith("/events/dlq"):
        return "sensitive"
    if path.startswith("/db/schema"):
        return "sensitive"
    for p in SENSITIVE_PREFIXES:
        if path.startswith(p):
            return "sensitive"
    return "public"


def _limit_for_class(settings: Any, klass: str, *, is_admin_mutate: bool) -> int:
    if is_admin_mutate:
        return int(settings.gateway_rl_admin_mutate_per_minute)
    if klass in ("admin", "sensitive"):
        return int(settings.gateway_rl_sensitive_per_minute)
    return int(settings.gateway_rl_public_per_minute)


class GatewayRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        redis_factory: Callable[[], Redis | None] | None = None,
    ) -> None:
        super().__init__(app)
        self._redis_factory = redis_factory or get_rate_limit_redis

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        settings = get_gateway_settings()
        path = request.url.path
        if path in ("/health", "/ready", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        if path.startswith("/v1/deploy/"):
            return await call_next(request)

        klass = _classify_path(path)
        is_mutate = request.method != "GET" and request.method != "HEAD"
        is_admin_mutate = path.startswith("/v1/admin") and is_mutate
        is_safety_mutate = _is_safety_mutation(path, request.method)
        wid = _client_bucket_key(request)
        window = 60
        if is_safety_mutate:
            limit = int(settings.gateway_rl_safety_mutate_per_minute)
            key = f"gateway:rl:safety_mutate:{wid}"
        elif is_admin_mutate:
            limit = _limit_for_class(settings, "admin", is_admin_mutate=True)
            key = f"gateway:rl:admin_mutate:{wid}"
        else:
            limit = _limit_for_class(settings, klass, is_admin_mutate=False)
            key = f"gateway:rl:{klass}:{wid}"

        redis_client = self._redis_factory()
        if redis_client is None:
            if settings.production:
                return Response(
                    content=json.dumps(
                        http_error_envelope(
                            status_code=503,
                            code="SERVICE_UNAVAILABLE",
                            message="Rate limit backend unavailable.",
                        )
                    ),
                    status_code=503,
                    media_type="application/json",
                )
            return await call_next(request)

        try:
            if is_safety_mutate:
                b_key = f"gateway:rl:burst_safety:{wid}"
                b_count = int(redis_client.incr(b_key))
                if b_count == 1:
                    redis_client.expire(b_key, 10)
                burst_cap = int(settings.gateway_rl_safety_burst_per_10s)
                if b_count > burst_cap:
                    logger.warning(
                        "gateway rate burst exceeded path=%s wid=%s count=%s cap=%s",
                        path,
                        wid,
                        b_count,
                        burst_cap,
                    )
                    if settings.production:
                        body = json.dumps(
                            http_error_envelope(
                                status_code=429,
                                code="RATE_LIMIT_BURST",
                                message="Safety mutation burst exceeded.",
                            )
                        )
                    else:
                        body = '{"detail":"safety burst rate limit exceeded"}'
                    return Response(
                        content=body,
                        status_code=429,
                        media_type="application/json",
                        headers={"Retry-After": "10"},
                    )
            count = int(redis_client.incr(key))
            if count == 1:
                redis_client.expire(key, window)
        except RedisError as exc:
            logger.warning("rate limit redis error: %s", exc)
            if settings.production:
                return Response(
                    content=json.dumps(
                        http_error_envelope(
                            status_code=503,
                            code="SERVICE_UNAVAILABLE",
                            message="Rate limit check failed.",
                        )
                    ),
                    status_code=503,
                    media_type="application/json",
                )
            return await call_next(request)

        if count > limit:
            if is_safety_mutate:
                logger.warning(
                    "gateway safety mutate rate exceeded path=%s wid=%s count=%s limit=%s",
                    path,
                    wid,
                    count,
                    limit,
                )
            if settings.production:
                body = json.dumps(
                    http_error_envelope(
                        status_code=429,
                        code="RATE_LIMIT_EXCEEDED",
                        message="Too many requests.",
                    )
                )
            else:
                body = '{"detail":"rate limit exceeded"}'
            return Response(
                content=body,
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window)},
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
