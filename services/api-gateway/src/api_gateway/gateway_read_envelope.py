"""
Einheitliche Leser-Envelope fuer Dashboard-BFF: keine rohen 500er, klare Texte fuer UI.

Felder (immer gesetzt):
- status: ok | empty | degraded (z. B. Live-State: `empty` = leer aber DB erreichbar)
- message: kurzer deutscher Nutzertext oder null
- empty_state: bool
- degradation_reason: Maschinencode oder null
- next_step: konkrete Handlungsempfehlung oder null
- read_envelope_contract_version: int (stabil fuer Clients/Logs; vgl. BFF in docs/INTERNAL_SERVICE_ROUTES.md)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from api_gateway.db import DatabaseHealthError, get_database_url

logger = logging.getLogger("api_gateway.db_read")

READ_ENVELOPE_CONTRACT_VERSION = 1

NEXT_STEP_DB = (
    "Postgres pruefen, Migration-Job ausfuehren. In Docker: DATABASE_URL auf den "
    "Service `postgres` zeigen lassen (z. B. BITGET_USE_DOCKER_DATASTORE_DSN=true)."
)


def merge_read_envelope(
    base: dict[str, Any],
    *,
    status: str,
    message: str | None = None,
    empty_state: bool = False,
    degradation_reason: str | None = None,
    next_step: str | None = None,
) -> dict[str, Any]:
    """Legt Kanalfelder ueber `base`; Envelope-Felder ueberschreiben Namenskollisionen in `base`."""
    return {
        **base,
        "status": status,
        "message": message,
        "empty_state": empty_state,
        "degradation_reason": degradation_reason,
        "next_step": next_step,
        "read_envelope_contract_version": READ_ENVELOPE_CONTRACT_VERSION,
    }


def safe_db_items(
    *,
    route_tag: str,
    limit: int,
    fetch: Callable[[Any], list[Any]],
    extra: dict[str, Any] | None = None,
    empty_reason: str = "no_rows",
    empty_message: str = "Keine Eintraege.",
    degraded_message: str = "Daten konnten nicht geladen werden.",
) -> dict[str, Any]:
    """Standardliste aus Postgres mit Envelope; kein HTTP-500 bei DB-Fehlern."""
    x = dict(extra or {})
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch(conn)
        payload = {"items": items, "limit": limit, **x}
        es = len(items) == 0
        return merge_read_envelope(
            payload,
            status="ok",
            message=empty_message if es else None,
            empty_state=es,
            degradation_reason=empty_reason if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("%s database_url: %s", route_tag, exc)
        return merge_read_envelope(
            {"items": [], "limit": limit, **x},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("%s db error: %s", route_tag, exc)
        return merge_read_envelope(
            {"items": [], "limit": limit, **x},
            status="degraded",
            message=degraded_message,
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
