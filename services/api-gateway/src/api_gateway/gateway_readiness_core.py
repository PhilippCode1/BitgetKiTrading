"""Gemeinsame Kern-Readiness fuer GET /ready (ohne Peer-URLs) und Abgleich in GET /v1/system/health.

Die drei Kernpruefungen (Postgres TCP, Schema/Migrations-Katalog laut get_db_health,
Redis PING) muessen mit der ersten Phase in ``app.ready`` identisch bleiben.
"""

from __future__ import annotations

import time
from typing import Any

from shared_py.observability import (
    check_postgres,
    check_redis_url_readiness,
    merge_ready_details,
)

from api_gateway.config import get_gateway_settings
from api_gateway.db import check_postgres_schema_for_ready
from api_gateway.readiness_util import effective_database_dsn, effective_redis_url

READINESS_CONTRACT_VERSION = 1
# Wenn nur Redis im ersten Snapshot ausfaellt, Postgres ok: kurz warten, dann zweiter Snapshot
# (vermeidet 500/False-Positives bei 50ms-Lastpeaks).
READINESS_REDIS_TRANSIENT_RECHECK_SEC = 0.15


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
        parts["redis"] = check_redis_url_readiness(
            rurl,
            max_attempts=int(s.gateway_readiness_redis_probe_max_attempts),
            budget_sec=float(s.gateway_readiness_redis_probe_budget_ms) / 1000.0,
            per_attempt_socket_sec=float(s.gateway_readiness_redis_probe_socket_sec),
        )
    else:
        parts["redis"] = (False, "missing REDIS_URL / REDIS_URL_DOCKER")
    return parts


def gateway_readiness_core_parts_resilient() -> dict[str, tuple[bool, str]]:
    """Wie :func:`gateway_readiness_core_parts_raw`, plus ein vollstaendiger Re-Check nach
    transiente-Redis-Flake, wenn beide Postgres-Kern-Checks true sind.
    """
    parts = gateway_readiness_core_parts_raw()
    if parts.get("redis", (True, ""))[0]:
        return parts
    s = get_gateway_settings()
    dsn = effective_database_dsn(s)
    rurl = effective_redis_url(s)
    if not dsn.strip() or not (rurl or "").strip():
        return parts
    if not (parts.get("postgres", (False, ""))[0] and parts.get("postgres_schema", (False, ""))[0]):
        return parts
    time.sleep(READINESS_REDIS_TRANSIENT_RECHECK_SEC)
    return gateway_readiness_core_parts_raw()


def gateway_readiness_core_snapshot() -> dict[str, Any]:
    """Kompakte Snapshot-Daten fuer System-Health (gleiche Logik wie /ready-Kern)."""
    parts = gateway_readiness_core_parts_resilient()
    core_ok, checks = merge_ready_details(parts)
    return {
        "contract_version": READINESS_CONTRACT_VERSION,
        "core_ok": core_ok,
        "checks": checks,
    }
