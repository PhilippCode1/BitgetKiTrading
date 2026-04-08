from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("api_gateway.db")

CORE_TABLES = (
    "app.schema_migrations",
    "app.news_items",
    "app.drawings",
    "app.signals",
    "app.demo_trades",
    "app.strategy_versions",
    "app.model_runs",
    "app.model_registry_v2",
    "app.audit_log",
    "tsdb.candles",
    "tsdb.trades",
    "tsdb.ticker",
    "tsdb.orderbook_top25",
    "tsdb.orderbook_levels",
    "tsdb.funding_rate",
    "tsdb.open_interest",
)

TABLE_COUNT_QUERIES = {
    "app.schema_migrations": "select count(*) as row_count from app.schema_migrations",
    "app.news_items": "select count(*) as row_count from app.news_items",
    "app.drawings": "select count(*) as row_count from app.drawings",
    "app.signals": "select count(*) as row_count from app.signals",
    "app.demo_trades": "select count(*) as row_count from app.demo_trades",
    "app.strategy_versions": "select count(*) as row_count from app.strategy_versions",
    "app.model_runs": "select count(*) as row_count from app.model_runs",
    "app.model_registry_v2": "select count(*) as row_count from app.model_registry_v2",
    "app.audit_log": "select count(*) as row_count from app.audit_log",
    "tsdb.candles": "select count(*) as row_count from tsdb.candles",
    "tsdb.trades": "select count(*) as row_count from tsdb.trades",
    "tsdb.ticker": "select count(*) as row_count from tsdb.ticker",
    "tsdb.orderbook_top25": "select count(*) as row_count from tsdb.orderbook_top25",
    "tsdb.orderbook_levels": "select count(*) as row_count from tsdb.orderbook_levels",
    "tsdb.funding_rate": "select count(*) as row_count from tsdb.funding_rate",
    "tsdb.open_interest": "select count(*) as row_count from tsdb.open_interest",
}

_MIGRATION_FILE_PREFIX = re.compile(r"^(\d+)_(.+)\.sql$", re.IGNORECASE)


def _migration_sort_key(path: Path) -> tuple[int, str]:
    """Gleiche Sortlogik wie infra/migrate.py (numerisches Praefix, dann Dateiname)."""
    m = _MIGRATION_FILE_PREFIX.match(path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (10**9, path.name)


def postgres_migrations_dir() -> Path | None:
    """
    Verzeichnis mit *.sql-Migrationen (fuer Abgleich mit app.schema_migrations).

    - Container-Image: /app/infra/migrations/postgres (Dockerfile COPY)
    - Optional: BITGET_POSTGRES_MIGRATIONS_DIR
    - Monorepo: …/infra/migrations/postgres relativ zu diesem Modul
    """
    env = (os.environ.get("BITGET_POSTGRES_MIGRATIONS_DIR") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    container = Path("/app/infra/migrations/postgres")
    if container.is_dir():
        return container
    try:
        root = Path(__file__).resolve().parents[4]
    except IndexError:
        return None
    p = root / "infra" / "migrations" / "postgres"
    return p if p.is_dir() else None


def list_expected_migration_filenames() -> list[str]:
    d = postgres_migrations_dir()
    if not d:
        return []
    paths = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".sql"]
    paths.sort(key=_migration_sort_key)
    return [p.name for p in paths]


class DatabaseHealthError(RuntimeError):
    pass


def get_database_url() -> str:
    from api_gateway.config import get_gateway_settings

    s = get_gateway_settings()
    dsn = s.database_url.strip()
    if not dsn:
        docker = str(getattr(s, "database_url_docker", "") or "").strip()
        if docker:
            dsn = docker
    if not dsn:
        raise DatabaseHealthError("DATABASE_URL fehlt")
    return dsn


def get_db_health() -> dict[str, Any]:
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            conn.execute("select 1")
            server_info = conn.execute(
                """
                select
                    current_database() as database_name,
                    current_schema() as current_schema,
                    now() as server_time
                """
            ).fetchone()
            existing_tables = _load_existing_tables(conn)
            missing_tables = [table for table in CORE_TABLES if table not in existing_tables]
            table_status = _collect_table_status(conn, existing_tables)

            migration_catalog_available = bool(postgres_migrations_dir())
            expected_files = list_expected_migration_filenames()
            pending_migrations: list[str] = []
            applied_filenames: list[str] = []
            if "app.schema_migrations" in existing_tables:
                applied_rows = conn.execute(
                    "SELECT filename FROM app.schema_migrations ORDER BY filename ASC"
                ).fetchall()
                applied_set = {str(row["filename"]) for row in applied_rows}
                applied_filenames = sorted(applied_set)
                if migration_catalog_available and expected_files:
                    pending_migrations = [f for f in expected_files if f not in applied_set]
            else:
                applied_filenames = []

            schema_core_ok = not missing_tables
            migrations_ok = (not migration_catalog_available) or (not pending_migrations)
            schema_alignment_ok = schema_core_ok and migrations_ok
            status = "ok" if schema_alignment_ok else "error"
    except psycopg.Error as exc:
        logger.warning("database health connect failed: %s", exc)
        raise DatabaseHealthError(str(exc)) from exc

    return {
        "status": status,
        "database": server_info["database_name"] if server_info is not None else None,
        "current_schema": server_info["current_schema"] if server_info is not None else None,
        "server_time": (
            server_info["server_time"].isoformat() if server_info is not None else None
        ),
        "missing_tables": missing_tables,
        "tables": table_status,
        "migration_catalog_available": migration_catalog_available,
        "expected_migration_files": len(expected_files),
        "applied_migration_files": len(applied_filenames),
        "pending_migrations": pending_migrations,
        "pending_migrations_preview": pending_migrations[:12],
        "schema_core_ok": schema_core_ok,
        "migrations_fully_applied": migrations_ok,
        "schema_alignment_ok": schema_alignment_ok,
    }


def get_applied_migrations() -> list[dict[str, Any]]:
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            rows = conn.execute(
                """
                select filename, applied_ts
                from app.schema_migrations
                order by applied_ts asc, filename asc
                """
            ).fetchall()
    except psycopg.Error as exc:
        logger.warning("schema migration lookup failed: %s", exc)
        raise DatabaseHealthError(str(exc)) from exc

    return [
        {
            "filename": row["filename"],
            "applied_ts": row["applied_ts"].isoformat(),
        }
        for row in rows
    ]


def check_postgres_schema_for_ready() -> tuple[bool, str]:
    """
    Kompakter Check fuer GET /ready: Kern-Tabellen + keine ausstehenden *.sql laut Katalog.
    """
    try:
        payload = get_db_health()
    except DatabaseHealthError as exc:
        return False, str(exc)
    if payload.get("status") == "ok":
        return True, "ok"
    missing = payload.get("missing_tables") or []
    pending = payload.get("pending_migrations") or []
    parts: list[str] = []
    if missing:
        parts.append(f"missing_core_tables={len(missing)}")
    if pending:
        parts.append(f"pending_migrations={len(pending)}")
    if not parts:
        parts.append("schema_not_ok")
    detail = "; ".join(parts)
    prev = payload.get("pending_migrations_preview") or []
    if prev:
        detail += f" (first: {', '.join(prev[:5])})"
    detail += " — run: python infra/migrate.py (DATABASE_URL)"
    return False, detail


def _load_existing_tables(conn: psycopg.Connection[Any]) -> set[str]:
    rows = conn.execute(
        """
        select schemaname, tablename
        from pg_catalog.pg_tables
        where schemaname in ('app', 'tsdb')
        order by schemaname asc, tablename asc
        """
    ).fetchall()
    return {f"{row['schemaname']}.{row['tablename']}" for row in rows}


def _collect_table_status(
    conn: psycopg.Connection[Any],
    existing_tables: set[str],
) -> dict[str, dict[str, Any]]:
    table_status: dict[str, dict[str, Any]] = {}
    for table_name in CORE_TABLES:
        exists = table_name in existing_tables
        row_count: int | None = None
        if exists:
            count_row = conn.execute(TABLE_COUNT_QUERIES[table_name]).fetchone()
            if count_row is not None:
                row_count = int(count_row["row_count"])
        table_status[table_name] = {
            "exists": exists,
            "row_count": row_count,
        }
    return table_status
