from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import psycopg

MIG_DIR = Path(__file__).resolve().parent / "migrations" / "postgres"
DEMO_MIG_DIR = Path(__file__).resolve().parent / "migrations" / "postgres_demo"
# Advisory-Lock-Key (beliebig, aber stabil) gegen parallele Migratoren
_MIGRATE_ADVISORY_LOCK_KEY = 0x62_69_74_67_65_74  # "bitget" als Hex-Fragmente


class MigrationError(Exception):
    """Fehler beim Anwenden einer einzelnen .sql-Datei."""

    def __init__(
        self,
        path: Path,
        message: str,
        *,
        pgcode: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.path = path
        self.pgcode = pgcode
        self.detail = detail
        super().__init__(message)


_MIGRATION_FILE_PREFIX = re.compile(r"^(\d+)_(.+)\.sql$", re.IGNORECASE)


def _migration_sort_key(path: Path) -> tuple[int, str]:
    """
    Numerisches Praefix (z. B. 020) vor lexikographischem Dateinamen.
    Verhindert falsche Reihenfolge bei unpadded Nummern (z. B. 20_ vor 100_).
    """
    m = _MIGRATION_FILE_PREFIX.match(path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (10**9, path.name)


def iter_migration_sql_paths(migrations_dir: Path) -> list[Path]:
    """
    Stabile Reihenfolge: nur Dateien, Suffix .sql (case-insensitive),
    sortiert nach numerischem Praefix, dann Dateiname.
    """
    if not migrations_dir.is_dir():
        raise RuntimeError(f"Migrationsverzeichnis fehlt oder ist kein Ordner: {migrations_dir}")
    out: list[Path] = []
    for p in migrations_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".sql":
            continue
        out.append(p)
    return sorted(out, key=_migration_sort_key)


def load_migration_sql(file_path: Path) -> str:
    """
    Laedt ausschliesslich lesbares UTF-8 (optional UTF-8-BOM).
    UTF-16 und Binaerdaten werden abgelehnt.
    """
    try:
        raw = file_path.read_bytes()
    except OSError as exc:
        raise MigrationError(file_path, f"Datei nicht lesbar: {exc}") from exc
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise MigrationError(
            file_path,
            "UTF-16 BOM erkannt — Migrationen muessen UTF-8 (ohne UTF-16) sein",
        )
    if b"\x00" in raw[:65536]:
        raise MigrationError(
            file_path,
            "Datei enthaelt NUL-Bytes — vermutlich binaer, nicht als SQL-Migration verwendbar",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MigrationError(
            file_path,
            f"Kein gueltiges UTF-8: {exc}",
        ) from exc
    if "\x00" in text:
        raise MigrationError(file_path, "NUL-Zeichen im dekodierten SQL-Text")
    sql = text.strip()
    if not sql:
        raise MigrationError(file_path, "Datei ist leer oder nur Whitespace")
    return sql


def _emit(emit: Callable[[str], None], msg: str) -> None:
    emit(msg)
    if hasattr(sys.stdout, "flush"):
        sys.stdout.flush()


def run_migrations(
    dsn: str,
    *,
    migrations_dir: Path | None = None,
    log: Callable[[str], None] | None = None,
    advisory_lock: bool = True,
) -> int:
    """
    Wendet alle noch nicht eingetragenen *.sql-Migrationen aus migrations_dir an.
    Gibt die Anzahl neu angewendeter Dateien zurueck.
    """
    mig_dir = migrations_dir or MIG_DIR
    emit = log or (lambda m: print(m, flush=True))

    files = iter_migration_sql_paths(mig_dir)
    if not files:
        raise RuntimeError(f"Keine gueltigen *.sql-Migrationsdateien in {mig_dir}")

    applied_count = 0
    skipped_count = 0
    dsn_stripped = dsn.strip()

    try:
        with psycopg.connect(dsn_stripped, autocommit=True, connect_timeout=30) as conn:
            if advisory_lock:
                conn.execute(
                    "SELECT pg_advisory_lock(%s::bigint)",
                    (_MIGRATE_ADVISORY_LOCK_KEY,),
                )
            try:
                conn.execute("SELECT 1")
                conn.execute("CREATE SCHEMA IF NOT EXISTS app")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app.schema_migrations (
                        filename text PRIMARY KEY,
                        applied_ts timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                applied_rows = conn.execute(
                    "SELECT filename FROM app.schema_migrations ORDER BY filename ASC"
                ).fetchall()
                applied = {row[0] for row in applied_rows}

                for file_path in files:
                    name = file_path.name
                    if name in applied:
                        skipped_count += 1
                        _emit(emit, f"[migrate] skip file={name} reason=already_applied")
                        continue

                    try:
                        sql = load_migration_sql(file_path)
                    except MigrationError as exc:
                        _emit(
                            emit,
                            f"[migrate] ERROR phase=read file={name} message={exc.args[0]}",
                        )
                        raise

                    try:
                        with conn.transaction():
                            conn.execute(sql)
                            conn.execute(
                                "INSERT INTO app.schema_migrations (filename) VALUES (%s)",
                                (name,),
                            )
                    except psycopg.Error as exc:
                        diag = exc.diag
                        pgcode = getattr(diag, "sqlstate", None) if diag else None
                        msg = getattr(diag, "message_primary", None) if diag else None
                        detail = getattr(diag, "message_detail", None) if diag else None
                        primary = msg or str(exc)
                        _emit(
                            emit,
                            f"[migrate] ERROR phase=execute file={name} "
                            f"sqlstate={pgcode or 'n/a'} message={primary}",
                        )
                        if detail:
                            _emit(emit, f"[migrate] ERROR file={name} detail={detail}")
                        raise MigrationError(
                            file_path,
                            primary,
                            pgcode=pgcode,
                            detail=detail,
                        ) from exc

                    applied_count += 1
                    _emit(emit, f"[migrate] applied file={name}")

                if applied_count == 0:
                    _emit(
                        emit,
                        f"[migrate] summary applied=0 skipped={skipped_count} "
                        f"(no pending migrations)",
                    )
                else:
                    _emit(
                        emit,
                        f"[migrate] summary applied={applied_count} skipped={skipped_count}",
                    )
            finally:
                if advisory_lock:
                    try:
                        conn.execute(
                            "SELECT pg_advisory_unlock(%s::bigint)",
                            (_MIGRATE_ADVISORY_LOCK_KEY,),
                        )
                    except psycopg.Error:
                        pass
    except psycopg.Error as exc:
        raise RuntimeError(f"[migrate] database error: {exc}") from exc

    return applied_count


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _demo_seed_run_resolution() -> tuple[Literal["run", "skip"], str | None]:
    """
    Gibt (run|skip, fatal_message) zurueck.
    fatal_message gesetzt => Aufrufer soll mit Exit 1 abbrechen (PRODUCTION + Demo-Flag).
    """
    allow = _truthy_env("BITGET_ALLOW_DEMO_SCHEMA_SEEDS")
    prod = _truthy_env("PRODUCTION")
    if prod and allow:
        return (
            "skip",
            "BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true zusammen mit PRODUCTION=true ist verboten",
        )
    if not allow:
        return ("skip", None)
    return ("run", None)


def run_demo_seed_migrations(
    dsn: str,
    *,
    log: Callable[[str], None] | None = None,
    advisory_lock: bool = True,
) -> int:
    """
    Wendet nur infra/migrations/postgres_demo/*.sql an (gleiche app.schema_migrations).
    Erfordert BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true und verbietet PRODUCTION=true.
    """
    emit = log or (lambda m: print(m, flush=True))
    mode, fatal = _demo_seed_run_resolution()
    if fatal:
        raise RuntimeError(fatal)
    if mode == "skip":
        _emit(
            emit,
            "[migrate] demo-seeds skipped "
            "(BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true fuer lokale Demo-INSERTs)",
        )
        return 0
    if not DEMO_MIG_DIR.is_dir():
        raise RuntimeError(
            "BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true aber postgres_demo-Verzeichnis fehlt: "
            f"{DEMO_MIG_DIR}"
        )
    paths = iter_migration_sql_paths(DEMO_MIG_DIR)
    if not paths:
        _emit(
            emit,
            "[migrate] demo-seeds: WARNUNG postgres_demo ohne .sql — nichts zu tun",
        )
        return 0
    return run_migrations(
        dsn,
        migrations_dir=DEMO_MIG_DIR,
        log=log,
        advisory_lock=advisory_lock,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Postgres-Schema-Migrationen (infra/migrations/postgres, optional postgres_demo)"
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="Alternatives Verzeichnis mit *.sql (Standard: infra/migrations/postgres)",
    )
    parser.add_argument(
        "--no-advisory-lock",
        action="store_true",
        help="Kein pg_advisory_lock (nur fuer Tests/Notfall)",
    )
    parser.add_argument(
        "--demo-seeds",
        action="store_true",
        help="Nur Demo-Seeds aus infra/migrations/postgres_demo (nach Hauptlauf aufrufen)",
    )
    args = parser.parse_args(argv)

    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("[migrate] ERROR DATABASE_URL fehlt", file=sys.stderr, flush=True)
        return 2

    try:
        if args.demo_seeds:
            run_demo_seed_migrations(
                dsn,
                advisory_lock=not args.no_advisory_lock,
            )
        else:
            mig_dir = args.migrations_dir
            run_migrations(
                dsn,
                migrations_dir=mig_dir,
                advisory_lock=not args.no_advisory_lock,
            )
    except MigrationError as exc:
        print(f"[migrate] FATAL {exc}", file=sys.stderr, flush=True)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
