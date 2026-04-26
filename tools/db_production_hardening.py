#!/usr/bin/env python3
"""
Produktions-Haertung: Verbindung zur DB, Seed-Locking (keine DUMMY-Strings in
Kern-Tabellen: app.instrument_catalog_entries, app.commercial_plan_definitions,
app.tenant_commercial_state; analog Forderung „instrument_catalog / commercial“),
Abgleich
  - MIGRATIONS: SHA-256 aller *.sql (Repo) vs. config/schema_master.hash
  - LIVE_APP_SCHEMA: laufendes app-Schema (Katalog) vs. Hash-Datei

config/schema_master.hash: siehe tools/refresh_schema_master_hash.py

Nur Migrations-Repo-Fingerprint (ohne Postgres)::

  python tools/db_production_hardening.py --migrations-fingerprint-only

Exit: 0 OK / 1 Fehler
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MIGFP = _ROOT / "tools" / "migrations_fingerprint.py"
_spec = importlib.util.spec_from_file_location("migrations_fingerprint", _MIGFP)
if _spec is None or _spec.loader is None:
    raise RuntimeError("migrations_fingerprint")
_mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mf)
compute_migrations_sha256 = _mf.compute_migrations_sha256

_SFP = _ROOT / "tools" / "live_app_schema_fingerprint.py"
_sfp = importlib.util.spec_from_file_location("live_app_schema_fingerprint", _SFP)
if _sfp is None or _sfp.loader is None:  # pragma: no cover
    raise RuntimeError("live_app_schema_fingerprint")
_lsf = importlib.util.module_from_spec(_sfp)
_sfp.loader.exec_module(_lsf)
compute_live_app_schema_sha256_from_conn = _lsf.compute_live_app_schema_sha256_from_conn

_SCHEMA_FILE = _ROOT / "config" / "schema_master.hash"

# Grossgeschrieben, um False Positives in Text zu vermeiden
_DEMO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"TEST_ID", re.IGNORECASE),
    re.compile(r"MOCK_USER", re.IGNORECASE),
    re.compile(r"PLACEHOLDER_USER", re.IGNORECASE),
)


def _parse_hash_file() -> dict[str, str]:
    if not _SCHEMA_FILE.is_file():
        return {}
    out: dict[str, str] = {}
    for line in _SCHEMA_FILE.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        for prefix in ("MIGRATIONS:", "LIVE_APP_SCHEMA:"):
            if t.startswith(prefix) and not t.lower().endswith("hash") and len(t) > 15:
                key = prefix.rstrip(":")
                out[key] = t.split(":", 1)[1].strip()
                break
    return out


def _read_expected_migrations_hash() -> str | None:
    p = _parse_hash_file()
    m = p.get("MIGRATIONS")
    if m:
        return m
    print(
        f"FAIL: MIGRATIONS:… in {_SCHEMA_FILE} fehlt oder leer",
        file=sys.stderr,
        flush=True,
    )
    return None


def _read_expected_live_app_schema_hash() -> str | None:
    p = _parse_hash_file()
    m = p.get("LIVE_APP_SCHEMA")
    if m:
        return m
    print(
        f"FAIL: LIVE_APP_SCHEMA:… in {_SCHEMA_FILE} fehlt — "
        "mit migrierter DB: python tools/refresh_schema_master_hash.py",
        file=sys.stderr,
        flush=True,
    )
    return None


def _check_schema_hash() -> bool:
    want = _read_expected_migrations_hash()
    if want is None:
        return False
    have = compute_migrations_sha256(_ROOT / "infra" / "migrations" / "postgres")
    if not have:
        print("FAIL: keine Migrationen?", file=sys.stderr, flush=True)
        return False
    if have != want:
        print(
            "FAIL: Migrations-Schema-Drift (SQL vs. schema_master.hash)",
            flush=True,
        )
        print(f"  erwartet: {want}", flush=True, file=sys.stderr)
        print(f"  ist:     {have}", flush=True, file=sys.stderr)
        return False
    print("OK: Migrations-Fingerprint = schema_master.hash (MIGRATIONS:)", flush=True)
    return True


def _check_live_app_schema(conn: object, want: str) -> bool:
    have = compute_live_app_schema_sha256_from_conn(conn)
    if have != want:
        print(
            "FAIL: app-Schema weicht von LIVE_APP_SCHEMA ab (schema_master.hash)",
            flush=True,
        )
        print(
            f"  erwartet: {want}",
            flush=True,
            file=sys.stderr,
        )
        print(f"  ist:      {have}", flush=True, file=sys.stderr)
        return False
    print("OK: LIVE_APP_SCHEMA (Katalog) = laufendes app-Schema", flush=True)
    return True


def _row_flags_demo_content(row: dict) -> str | None:
    blob = str(row)
    for pat in _DEMO_PATTERNS:
        if pat.search(blob):
            return f"Pattern {pat.pattern!r} in: {list(row.keys())[:5]}..."
    return None


def _check_seed_leaks(conn) -> bool:
    """Fahne Test-Demo-Strings; Kerntabellen fehlen nicht (kein stilles Weglassen)."""
    checks: list[tuple[str, str]] = [
        (
            """
            SELECT canonical_instrument_id, symbol, metadata_source,
                   symbol_aliases_json::text
            FROM app.instrument_catalog_entries
            LIMIT 5000
            """,
            "app.instrument_catalog_entries",
        ),
        (
            """
            SELECT plan_id, display_name, entitlements_json::text,
                   transparency_note
            FROM app.commercial_plan_definitions
            """,
            "app.commercial_plan_definitions",
        ),
        (
            "SELECT tenant_id, plan_id FROM app.tenant_commercial_state",
            "app.tenant_commercial_state",
        ),
    ]
    for sql, label in checks:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                for row in cur.execute(sql).fetchall() or ():
                    hit = _row_flags_demo_content({k: row[k] for k in row})
                    if hit is not None:
                        print(
                            f"ALARM: Seed-Lock: verdaechtiger Inhalt in {label}: {hit}",
                            file=sys.stderr,
                            flush=True,
                        )
                        return False
        except Exception as exc:  # noqa: BLE001
            emsg = f"{type(exc).__name__}: {exc!s}"
            if "does not exist" in emsg.lower() or "undefinedtable" in emsg.lower():
                print(
                    f"FAIL: Kerntabelle {label} fehlt (Migration nicht angewandt?)",
                    file=sys.stderr,
                    flush=True,
                )
                return False
            print(
                f"FAIL: Abfrage {label}: {exc!s}",
                file=sys.stderr,
                flush=True,
            )
            return False
    print(
        "OK: seed-locking (kein TEST_ID/MOCK_USER/… in geprueften Zeilen)",
        flush=True,
    )
    return True


def main() -> int:
    if "--migrations-fingerprint-only" in sys.argv[1:]:
        ok = _check_schema_hash()
        if not ok:
            return 1
        print(
            "OK: --migrations-fingerprint-only "
            "(Repo-SQL vs. schema_master.hash MIGRATIONS:)",
            flush=True,
        )
        return 0

    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print(
            "FAIL: DATABASE_URL fehlt (Produktions-Haertung)",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if not _check_schema_hash():
        return 1
    want_live = _read_expected_live_app_schema_hash()
    if want_live is None:
        return 1
    try:
        with psycopg.connect(dsn, connect_timeout=20, row_factory=dict_row) as conn:
            if not _check_live_app_schema(conn, want_live):
                return 1
            if not _check_seed_leaks(conn):
                return 1
    except Exception as exc:  # noqa: BLE001
        print(
            f"FAIL: Postgres / Haertung: {exc!s}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print("SUCCESS: db_production_hardening", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
