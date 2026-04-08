"""
DSN-Hilfen: oeffentliche Metadaten ohne Passwoerter; Logging fuer Betrieb.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote, urlparse


def public_meta_postgres(dsn: str) -> dict[str, Any]:
    """Host, Port, DB-Name, DB-User — niemals Passwort."""
    raw = (dsn or "").strip()
    if not raw:
        return {"host": "", "port": None, "dbname": "", "user": ""}
    p = urlparse(raw)
    host = p.hostname or ""
    port = p.port
    if port is None and p.scheme in ("postgresql", "postgres", "postgresql+psycopg"):
        port = 5432
    dbname = (p.path or "").lstrip("/").split("?", 1)[0] if p.path else ""
    user = unquote(p.username) if p.username else ""
    return {"host": host, "port": port, "dbname": dbname, "user": user}


def public_meta_redis(url: str) -> dict[str, Any]:
    raw = (url or "").strip()
    if not raw:
        return {"host": "", "port": None}
    p = urlparse(raw)
    host = p.hostname or ""
    port = p.port if p.port is not None else 6379
    return {"host": host, "port": port}


def log_effective_datastores(logger: logging.Logger, settings: Any) -> None:
    """
    Einmaliger Hinweis nach Settings-Load: Ziel-Datastore ohne Secrets.
    `source`: docker = BITGET_USE_DOCKER_DATASTORE_DSN (Compose-Pfad), sonst host.
    """
    use_docker = bool(getattr(settings, "use_docker_datastore_dsn", False))
    src = "docker" if use_docker else "host"

    du = str(getattr(settings, "database_url", "") or "").strip()
    if du:
        m = public_meta_postgres(du)
        logger.info(
            "datastore_postgres_effective host=%s port=%s db=%s db_user=%s source=%s",
            m["host"],
            m["port"],
            m["dbname"],
            m["user"],
            src,
        )
    else:
        logger.warning("datastore_postgres_effective missing DATABASE_URL source=%s", src)

    ru = str(getattr(settings, "redis_url", "") or "").strip()
    if ru:
        m = public_meta_redis(ru)
        logger.info(
            "datastore_redis_effective host=%s port=%s source=%s",
            m["host"],
            m["port"],
            src,
        )
    else:
        logger.warning("datastore_redis_effective missing REDIS_URL source=%s", src)
