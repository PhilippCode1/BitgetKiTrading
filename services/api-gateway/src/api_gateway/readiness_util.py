"""Hilfen fuer Gateway-Readiness (/ready) — konsistente DSN-Aufloesung."""

from __future__ import annotations

from typing import Any


def effective_database_dsn(settings: Any) -> str:
    d = str(getattr(settings, "database_url", "") or "").strip()
    if d:
        return d
    return str(getattr(settings, "database_url_docker", "") or "").strip()


def effective_redis_url(settings: Any) -> str:
    r = str(getattr(settings, "redis_url", "") or "").strip()
    if r:
        return r
    return str(getattr(settings, "redis_url_docker", "") or "").strip()
