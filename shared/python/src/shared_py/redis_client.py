"""
Zentrale Redis-Connection-Parameter: Pools, Timeouts, Keepalive, Init-Backoff.

Fuer sync: ``redis.ConnectionPool`` + ``redis.Redis``; fuer async:
``redis.asyncio.ConnectionPool`` + ``redis.asyncio.Redis`` (kein lose ``from_url``-Client
ohne Pool).

Schneller Init-Backoff in Tests/CI: ``REDIS_INIT_RECONNECT_FAST=1`` nutzt millisekundenahe
Pausen statt 1/2/4/… s bis max. 10 s (:func:`connect_sync_redis_with_init_backoff`).
"""

from __future__ import annotations

import os
import random
import re
import threading
import time

import redis
import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.client import ConnectionPool

_DEFAULT_MAX_CONNECTIONS = 32
_DEFAULT_SOCKET_CONNECT = 5.0
_DEFAULT_SOCKET = 5.0
# Erstverbindung/Retry zwischen Versuchen (Produktion): 1s, 2s, 4s, ... max. 10s
_INIT_RECONNECT_CAP_SEC = 10.0

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


def init_reconnect_backoff_sec(attempt: int) -> float:
    """Pausen zwischen fehlgeschlagenen Erstverbindungs-Versuchen: 1, 2, 4, ... s (max. 10), mit leichtem Jitter."""
    t = min(_INIT_RECONNECT_CAP_SEC, 1.0 * (2.0**float(attempt)))
    if t <= 0:
        return 0.0
    j = 1.0 + 0.04 * random.random()
    return t * j


def _sleep_init_reconnect_backoff(attempt: int) -> None:
    """Produktions-Backoff, oder bei REDIS_INIT_RECONNECT_FAST kurze Delays (Tests/CI)."""
    if (os.environ.get("REDIS_INIT_RECONNECT_FAST") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        t = exponential_backoff_sec(attempt, base=0.05, cap=0.5)
    else:
        t = init_reconnect_backoff_sec(attempt)
    if t > 0:
        time.sleep(t)


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
            socket_connect_timeout=_DEFAULT_SOCKET_CONNECT,
            socket_timeout=_DEFAULT_SOCKET,
            socket_keepalive=True,
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
            _sleep_init_reconnect_backoff(attempt)
    return None


class TenantNamespacedSyncRedis:
    """
    P76: Redis-Key-Namespace pro Mandant (z. B. ``tenant:default:signal_cache``), um
    Kollisionsfälle im gemeinsamen Redis zu verhindern. Nicht geeignet für
    plattformweite Kanäle (z. B. unbenanntes PUBLISH) — dafür den rohen Client nutzen.
    """

    __slots__ = ("_prefix", "_r")

    def __init__(self, client: redis.Redis, tenant_id: str) -> None:
        self._r = client
        self._prefix = _tenant_id_redis_prefix(tenant_id)

    @property
    def raw(self) -> redis.Redis:
        return self._r

    def k(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, name: str) -> str | None:
        return self._r.get(self.k(name))  # type: ignore[no-any-return]

    def set(
        self,
        name: str,
        value: str | int | float | bool | None,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        return self._r.set(self.k(name), value, ex=ex, px=px, nx=nx, xx=xx)  # type: ignore[no-any-return]

    def setex(  # noqa: A003
        self, name: str, ttl_seconds: int, value: str | int | float | bool | None
    ) -> bool:
        return self._r.setex(self.k(name), ttl_seconds, value)  # type: ignore[no-any-return]

    def delete(self, *names: str) -> int:
        return int(self._r.delete(*[self.k(n) for n in names]))

    def exists(self, *names: str) -> int:
        return int(self._r.exists(*[self.k(n) for n in names]))  # type: ignore[no-any-return]

    def incr(self, name: str, amount: int = 1) -> int:
        return int(self._r.incr(self.k(name), amount))  # type: ignore[no-any-return]

    def mget(self, *keys: str) -> list[str | None]:
        return self._r.mget(*[self.k(k) for k in keys])  # type: ignore[no-any-return]

    def hget(self, name: str, key: str) -> str | None:
        return self._r.hget(self.k(name), key)  # type: ignore[no-any-return]

    def hset(  # noqa: A001
        self,
        name: str,
        key: str,
        value: str | int | float | bool | None,
    ) -> int:
        return int(self._r.hset(self.k(name), key, value))  # type: ignore[no-any-return]


def wrap_sync_redis_tenant(
    client: redis.Redis,
    tenant_id: str,
) -> TenantNamespacedSyncRedis:
    return TenantNamespacedSyncRedis(client, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# P76: öffentliches Präfix — auch fuer Stream-/Rate-Key-Namen in Handcode nutzbar
# ---------------------------------------------------------------------------


_RE_TENANT_RKEY = re.compile(r"^[\w.\-]{1,128}$", re.ASCII)


def _redis_tenant_token(tenant_id: str) -> str:
    s = (tenant_id or "").strip()
    if not s or not _RE_TENANT_RKEY.match(s):
        raise ValueError("invalid_tenant_id_for_redis_namespace")
    return s


def _tenant_id_redis_prefix(tenant_id: str) -> str:
    t = _redis_tenant_token(tenant_id)
    return f"tenant:{t}:"


def build_tenant_redis_key(tenant_id: str, *parts: str) -> str:
    path = "/".join(p for p in parts if (p or "").strip())
    if ".." in path or path.startswith("/"):
        raise ValueError("invalid_key_parts")
    b = f"{_tenant_id_redis_prefix(tenant_id)}{path}"
    if len(b) > 512:
        raise ValueError("redis_tenant_key_too_long")
    return b


def apply_chaos_latency_to_sync_redis(
    client: redis.Redis,
    *,
    every_n: int = 10,
    delay_sec: float = 6.0,
) -> redis.Redis:
    """
    Test-/Chaos-Layer: injiziert in ``execute_command`` periodische Verzoegerung
    (siehe :func:`shared_py.chaos.infra_chaos.wrap_redis_with_chaos_latency`).
    """
    from shared_py.chaos.infra_chaos import wrap_redis_with_chaos_latency

    return wrap_redis_with_chaos_latency(
        client, every_n=every_n, delay_sec=delay_sec
    )
