"""Gemeinsame Kern-Readiness fuer GET /ready (ohne Peer-URLs) und Abgleich in GET /v1/system/health.

Die drei Kernpruefungen (Postgres TCP, Schema/Migrations-Katalog laut get_db_health,
Redis PING) muessen mit der ersten Phase in ``app.ready`` identisch bleiben.
"""

from __future__ import annotations

from typing import Any

from shared_py.observability import check_postgres, check_redis_url, merge_ready_details

from api_gateway.config import get_gateway_settings
from api_gateway.db import check_postgres_schema_for_ready
from api_gateway.readiness_util import effective_database_dsn, effective_redis_url

READINESS_CONTRACT_VERSION = 1


def gateway_readiness_core_parts_raw() -> dict[str, tuple[bool, str]]:
    """Nur Postgres, Schema-Katalog, Redis — wie die erste Phase in ``create_app().ready``."""
    s = get_gateway_settings()
    dsn = effective_database_dsn(s)
    rurl = effective_redis_url(s)
    if dsn.strip():
        schema_ok, schema_detail = check_postgres_schema_for_ready()
        parts: dict[str, tuple[bool, str]] = {
            "postgres": check_postgres(dsn),
            "postgres_schema": (schema_ok, schema_detail),
        }
    else:
        parts = {
            "postgres": (False, "missing database DSN (DATABASE_URL*)"),
            "postgres_schema": (
                False,
                "no DATABASE_URL / DATABASE_URL_DOCKER — postgres_schema not evaluated",
            ),
        }
    if rurl:
        parts["redis"] = check_redis_url(rurl)
    else:
        parts["redis"] = (False, "missing REDIS_URL / REDIS_URL_DOCKER")
    return parts


def gateway_readiness_core_snapshot() -> dict[str, Any]:
    """Kompakte Snapshot-Daten fuer System-Health (gleiche Logik wie /ready-Kern)."""
    parts = gateway_readiness_core_parts_raw()
    core_ok, checks = merge_ready_details(parts)
    return {
        "contract_version": READINESS_CONTRACT_VERSION,
        "core_ok": core_ok,
        "checks": checks,
    }
