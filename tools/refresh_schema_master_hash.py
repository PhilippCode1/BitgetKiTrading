#!/usr/bin/env python3
"""
Aktualisiert config/schema_master.hash:
  - MIGRATIONS: SHA-256 aller infra/migrations/postgres/*.sql
  - LIVE_APP_SCHEMA: SHA-256 laufendes Katalog-Schema (app), benoetigt DATABASE_URL

Nur MIGRATIONS ohne DB: alte LIVE_APP_SCHEMA in der Datei bleibt (nach
Migrations-Wechsel mit DB + DATABASE_URL erneut ausfuehren).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import psycopg

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "config" / "schema_master.hash"
_MIG = _ROOT / "infra" / "migrations" / "postgres"


def _load_modules() -> tuple[object, object]:
    p_m = _ROOT / "tools" / "migrations_fingerprint.py"
    s_m = importlib.util.spec_from_file_location("migrations_fingerprint", p_m)
    if s_m is None or s_m.loader is None:
        raise RuntimeError("migrations_fingerprint")
    m_m = importlib.util.module_from_spec(s_m)
    s_m.loader.exec_module(m_m)
    p_l = _ROOT / "tools" / "live_app_schema_fingerprint.py"
    s_l = importlib.util.spec_from_file_location("live_app_schema_fingerprint", p_l)
    if s_l is None or s_l.loader is None:
        raise RuntimeError("live_app_schema_fingerprint")
    m_l = importlib.util.module_from_spec(s_l)
    s_l.loader.exec_module(m_l)
    return m_m, m_l


def _parse_old_live() -> str:
    if not _OUT.is_file():
        return ""
    for line in _OUT.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t.startswith("LIVE_APP_SCHEMA:") and not t.rstrip().endswith("hash"):
            return t.split(":", 1)[1].strip()
    return ""


def main() -> int:
    mmod, lmod = _load_modules()
    m_hash: str = mmod.compute_migrations_sha256(_MIG)
    if not m_hash:
        print("FAIL: keine Migrations-*.sql", file=sys.stderr)
        return 1
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if dsn:
        try:
            with psycopg.connect(dsn, connect_timeout=20) as conn:
                l_hash: str = lmod.compute_live_app_schema_sha256_from_conn(conn)
        except Exception as exc:  # noqa: BLE001
            print(
                f"FAIL: Konnte LIVE_APP_SCHEMA nicht erzeugen: {exc!s}",
                file=sys.stderr,
            )
            return 1
    else:
        l_hash = _parse_old_live()
        if not l_hash:
            print(
                "FAIL: Kein DATABASE_URL und kein gueltiger LIVE_APP_SCHEMA:… in der "
                f"Datei; gebe z. B. {_OUT!s} nach Migrationen mit DSN an.",
                file=sys.stderr,
            )
            return 1
        print(
            "WARN: DATABASE_URL leer – LIVE_APP_SCHEMA in der Datei unveraendert "
            "(nach SQL-Aenderung bitte mit DB erneut ausfuehren).",
            flush=True,
        )
    header = (
        "# MIGRATIONS: SHA-256 aller .sql-Dateien (Sortierung deterministisch).\n"
        "# LIVE_APP_SCHEMA: Katalog-Hash (app), braucht DATABASE_URL (migrierte DB).\n"
        "# python tools/refresh_schema_master_hash.py\n"
    )
    _OUT.write_text(
        header + f"MIGRATIONS:{m_hash}\nLIVE_APP_SCHEMA:{l_hash}\n",
        encoding="utf-8",
    )
    print(
        "OK",
        str(_OUT),
        "MIGRATIONS",
        m_hash[:12] + "…",
        "LIVE_APP_SCHEMA",
        l_hash[:12] + "…",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
