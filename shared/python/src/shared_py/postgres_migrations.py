"""
Gemeinsame Logik: Verzeichnis der SQL-Migrationen (infra/migrations/postgres) und
Dateiliste — dieselbe Quelle wie api_gateway.db / migrate.py.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_MIGRATION_FILE_PREFIX = re.compile(r"^(\d+)_(.+)\.sql$", re.IGNORECASE)


def migration_sort_key(path: Path) -> tuple[int, str]:
    m = _MIGRATION_FILE_PREFIX.match(path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (10**9, path.name)


def repo_root_from_shared_py() -> Path:
    """Monorepo-Root von shared/python/src/shared_py/..."""
    return Path(__file__).resolve().parents[4]


def postgres_migrations_dir() -> Path | None:
    """
    Verzeichnis mit *.sql-Migrationen (Abgleich mit app.schema_migrations).

    - Container-Image: /app/infra/migrations/postgres
    - Optional: BITGET_POSTGRES_MIGRATIONS_DIR
    - Monorepo: …/infra/migrations/postgres
    """
    env = (os.environ.get("BITGET_POSTGRES_MIGRATIONS_DIR") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    container = Path("/app/infra/migrations/postgres")
    if container.is_dir():
        return container
    root = repo_root_from_shared_py()
    p = root / "infra" / "migrations" / "postgres"
    return p if p.is_dir() else None


def list_expected_migration_filenames() -> list[str]:
    d = postgres_migrations_dir()
    if not d:
        return []
    paths = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".sql"]
    paths.sort(key=migration_sort_key)
    return [p.name for p in paths]


def expected_head_migration_filename() -> str | None:
    files = list_expected_migration_filenames()
    return files[-1] if files else None
