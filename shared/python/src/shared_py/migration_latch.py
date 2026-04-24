"""
Migration-Latch: Repo-Migrationskatalog (infra/migrations/postgres) abgleichen mit
app.schema_migrations — bei fehlenden Dateien: harter Start-Stop.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from shared_py.postgres_migrations import (
    list_expected_migration_filenames,
    postgres_migrations_dir,
)


class MigrationMismatchError(RuntimeError):
    """Wird bei fehlendem Eintrag in app.schema_migrations geworfen."""


def _format_mismatch(
    pending: list[str], *, head: str | None
) -> str:
    prev = (pending or [])[:8]
    tail = "…" if len(pending) > 8 else ""
    base = f"Migration Mismatch: {len(pending)} pending repo migration(s) not in app.schema_migrations"
    if head:
        base += f"; head expected={head!r}"
    if prev:
        base += f" (pending sample: {', '.join(repr(p) for p in prev)}{tail})"
    base += " — run: python infra/migrate.py (DATABASE_URL)"
    return base


def assert_repo_migrations_applied_sync(
    dsn: str, *, connect_timeout: float = 8.0
) -> None:
    """
    Synchron: alle erwarteten *.sql-Dateien muessen in app.schema_migrations stehen.
    Leerer Katalog oder fehlendes Migrationsverzeichnis: no-op.
    """
    d = postgres_migrations_dir()
    if not d:
        return
    expected = list_expected_migration_filenames()
    if not expected:
        return
    head = expected[-1] if expected else None
    if (os.environ.get("BITGET_SKIP_MIGRATION_LATCH") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    with psycopg.connect(
        dsn, row_factory=dict_row, connect_timeout=connect_timeout
    ) as conn:
        pending = _pending_against_db(conn, expected)
    if pending:
        raise MigrationMismatchError(
            _format_mismatch(pending, head=head),
        )


def _pending_against_db(
    conn: Any,
    expected: list[str],
) -> list[str]:
    try:
        cur = conn.execute("SELECT filename FROM app.schema_migrations")
        rows: list = cur.fetchall() or []
    except Exception:  # noqa: BLE001
        raise MigrationMismatchError(
            "Migration Mismatch: app.schema_migrations not readable (apply migrations: "
            "python infra/migrate.py)"
        ) from None
    applied = {
        str(r["filename"]) for r in rows if r and (r.get("filename") is not None)
    }
    return [f for f in expected if f not in applied]


async def assert_repo_migrations_applied_async(engine: AsyncEngine) -> None:
    if (os.environ.get("BITGET_SKIP_MIGRATION_LATCH") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    d = postgres_migrations_dir()
    if not d:
        return
    expected = list_expected_migration_filenames()
    if not expected:
        return
    head = expected[-1] if expected else None
    try:
        async with engine.connect() as conn:
            try:
                r = await conn.execute(
                    text("SELECT filename FROM app.schema_migrations")
                )
                maps = r.mappings().all()
            except Exception:
                raise MigrationMismatchError(
                    "Migration Mismatch: app.schema_migrations not readable (apply "
                    "migrations: python infra/migrate.py)"
                ) from None
            applied = {str(m["filename"]) for m in maps if m.get("filename")}
            pending = [f for f in expected if f not in applied]
            if pending:
                raise MigrationMismatchError(
                    _format_mismatch(pending, head=head),
                )
    except MigrationMismatchError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MigrationMismatchError(
            f"Migration Mismatch: database probe failed: {type(exc).__name__}: {exc!s}"
        ) from exc
