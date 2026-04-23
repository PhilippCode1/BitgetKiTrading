"""
Zentrale Redis-Connection-Parameter: Pools, Timeouts, Keepalive, Init-Backoff.

Fuer sync: ``redis.ConnectionPool`` + ``redis.Redis``; fuer async: ``redis.asyncio``.
"""

from __future__ import annotations

import random
import threading
import time
import redis
import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.client import ConnectionPool

_DEFAULT_MAX_CONNECTIONS = 32
_DEFAULT_SOCKET_CONNECT = 5.0
_DEFAULT_SOCKET = 5.0

_sync_cache: dict[str, tuple[ConnectionPool, redis.Redis]] = {}
_sync_cache_lock = threading.RLock()

_async_cache: dict[str, tuple[AsyncConnectionPool, aioredis.Redis]] = {}
_async_lock = threading.RLock()


def _pool_cache_key(
    url: str,
    *,
    decode_responses: bool,
    max_connections: int,
    kind: str,
) -> str:
    return f"{kind}|{url}|decode={decode_responses}|m={max_connections}"


def exponential_backoff_sec(attempt: int, *, base: float = 0.08, cap: float = 2.0) -> float:
    """0-basierter Versuch: 0,1,2,... -> base*2^attempt (mit kleinem Jitter)."""
    t = min(cap, base * (2.0**float(attempt)))
    if t <= 0:
        return 0.0
    j = 1.0 + 0.05 * random.random()
    return t * j


def create_sync_connection_pool(
    url: str,
    *,
    decode_responses: bool = True,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    socket_connect_timeout: float = _DEFAULT_SOCKET_CONNECT,
    socket_timeout: float = _DEFAULT_SOCKET,
    socket_keepalive: bool = True,
    health_check_interval: int = 0,
) -> ConnectionPool:
    """Gemeinsame Pool-Factory fuer sync-Redis (read/write)."""
    return ConnectionPool.from_url(
        url,
        decode_responses=decode_responses,
        max_connections=int(max_connections),
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
        socket_keepalive=socket_keepalive,
        health_check_interval=health_check_interval,
    )


def sync_redis_from_pool(pool: ConnectionPool, *, health_check_interval: int = 30) -> redis.Redis:
    return redis.Redis(connection_pool=pool, health_check_interval=health_check_interval)


def create_async_connection_pool(
    url: str,
    *,
    decode_responses: bool = True,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    socket_connect_timeout: float = _DEFAULT_SOCKET_CONNECT,
    socket_timeout: float = _DEFAULT_SOCKET,
    socket_keepalive: bool = True,
    health_check_interval: int = 0,
) -> AsyncConnectionPool:
    return AsyncConnectionPool.from_url(
        url,
        decode_responses=decode_responses,
        max_connections=int(max_connections),
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
        socket_keepalive=socket_keepalive,
        health_check_interval=health_check_interval,
    )


def async_redis_from_pool(
    pool: AsyncConnectionPool, *, health_check_interval: int = 30
) -> aioredis.Redis:
    return aioredis.Redis(connection_pool=pool, health_check_interval=health_check_interval)


def get_or_create_sync_pooled_client(
    url: str,
    *,
    role: str,
    decode_responses: bool = True,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    health_check_interval: int = 30,
) -> redis.Redis:
    """
    Wiederverwendbares (process-lokales) ``Redis``-Objekt mit Hintergrund-Pool.
    ``role`` muss pro Verwendung eindeutig sein (z.B. rate_limit, events, probe).
    """
    u = (url or "").strip()
    if not u:
        raise ValueError("get_or_create_sync_pooled_client: empty url")
    k = _pool_cache_key(
        u, decode_responses=decode_responses, max_connections=max_connections, kind=role
    )
    with _sync_cache_lock:
        if k in _sync_cache:
            return _sync_cache[k][1]
        pool = create_sync_connection_pool(
            u,
            decode_responses=decode_responses,
            max_connections=max_connections,
        )
        client = sync_redis_from_pool(pool, health_check_interval=health_check_interval)
        _sync_cache[k] = (pool, client)
        return client


def get_or_create_async_pooled_client(
    url: str,
    *,
    role: str,
    decode_responses: bool = True,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    health_check_interval: int = 30,
) -> aioredis.Redis:
    u = (url or "").strip()
    if not u:
        raise ValueError("get_or_create_async_pooled_client: empty url")
    k = _pool_cache_key(
        u, decode_responses=decode_responses, max_connections=max_connections, kind=role
    )
    with _async_lock:
        if k in _async_cache:
            return _async_cache[k][1]
        pool = create_async_connection_pool(
            u,
            decode_responses=decode_responses,
            max_connections=max_connections,
        )
        client = async_redis_from_pool(pool, health_check_interval=health_check_interval)
        _async_cache[k] = (pool, client)
        return client


def connect_sync_redis_with_init_backoff(
    url: str,
    *,
    decode_responses: bool = True,
    max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    init_retries: int = 4,
) -> tuple[ConnectionPool, redis.Redis] | None:
    """
    Erstverbindung mit kurzem exponentiellem Backoff (z.B. API-Gateway Rate-Limit).
    Bei dauerhaftem Fehlschlag: Pool trennen und None.
    """
    u = (url or "").strip()
    if not u:
        return None
    n = int(init_retries)
    for attempt in range(n):
        pool = create_sync_connection_pool(
            u,
            decode_responses=decode_responses,
            max_connections=int(max_connections),
        )
        client = sync_redis_from_pool(pool, health_check_interval=30)
        ok = False
        try:
            ok = bool(client.ping())
        except Exception:
            ok = False
        if ok:
            return pool, client
        try:
            client.close()
        except Exception:
            pass
        try:
            pool.disconnect()
        except Exception:
            pass
        if attempt < n - 1:
            time.sleep(exponential_backoff_sec(attempt))
    return None
