#!/usr/bin/env python3
"""
Self-Check: Modul-Mate-Execution-Gates (Migration 604 + Live-Broker-Policy).

- Ohne profilierenden Deploy-Kontext (siehe _needs_database_url):
  Datei- und shared_py-Import-Pruefungen; ohne DATABASE_URL → SKIP, Exit 0.
- Mit APP_ENV=production|staging, PRODUCTION=true oder APP_ENV=shadow
  (oder explizit SELFCHECK_DATABASE_REQUIRED=1): DATABASE_URL PFLICHT —
  fehlend oder nicht verbindbar → **Exit 1** (kein verschleierndes SKIP).

M604-Schema: physische Tabelle app.tenant_modul_mate_gates (siehe
``shared_py.modul_mate_db_gates``). Standard-Seed tenant ``default`` muss
den INSERT aus 604 entsprechen, sofern tenant_id=default geprueft wird.

Exit: 0 OK / 1 Fehler
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _norm_truthy(val: str | None) -> bool:
    s = (val or "").strip().lower()
    return s in ("1", "true", "yes", "on")


def _selfcheck_requires_database_url() -> tuple[bool, str]:
    """
    True, wenn fehlendes/ungenutztes DATABASE_URL in diesem Kontext
    inakzeptabel ist (Release-50-Bug: SKIP bei prod ohne DB = Exit 0).
    """
    if _norm_truthy(os.environ.get("SELFCHECK_DATABASE_REQUIRED")):
        return True, "SELFCHECK_DATABASE_REQUIRED=1 (explizit)"
    if _norm_truthy(os.environ.get("PRODUCTION")):
        return True, "PRODUCTION=1 (prod-like, Release-Gate-Profil)"
    app_env = (os.environ.get("APP_ENV") or "development").strip().lower()
    if app_env in ("production", "staging", "shadow"):
        return True, f"APP_ENV={app_env!r} (produktiv, Staging- oder Shadow-Paritaet)"
    return False, ""


def _emit_missing_env_help() -> None:
    print(
        "FAIL: Datenbank-Selfcheck in diesem Profil PFLICHT, aber DATABASE_URL "
        "ist nicht gesetzt oder leer.",
        flush=True,
    )
    print(
        "  Erforderliche Variable: DATABASE_URL "
        "(Postgres-DSN, z. B. postgresql://USER:PASS@HOST:5432/DBNAME)",
        flush=True,
    )
    print(
        "  Weitere, relevante Anzeiger im aktuellen Umfeld: PRODUCTION, APP_ENV, "
        "SELFCHECK_DATABASE_REQUIRED, MODUL_MATE_GATE_TENANT_ID (default: default).",
        flush=True,
    )
    _ev = ("PRODUCTION", "APP_ENV", "SELFCHECK_DATABASE_REQUIRED")
    c = {k: os.environ.get(k) for k in _ev}
    print(
        f"  Aktuell: PRODUCTION={c['PRODUCTION']!r}, "
        f"APP_ENV={c['APP_ENV']!r}, "
        f"SELFCHECK_DATABASE_REQUIRED={c['SELFCHECK_DATABASE_REQUIRED']!r}",
        flush=True,
    )


def main() -> int:
    root = _repo_root()
    requires_db, prof_reason = _selfcheck_requires_database_url()
    mig = (
        root
        / "infra"
        / "migrations"
        / "postgres"
        / "604_modul_mate_execution_gates.sql"
    )
    if not mig.is_file():
        print("FAIL: Migration 604 fehlt:", mig)
        return 1
    migrate_runner = root / "infra" / "migrate.py"
    if not migrate_runner.is_file():
        print(
            "FAIL: infra/migrate.py fehlt (Migrationen nicht anwendbar):",
            migrate_runner,
        )
        return 1
    shared_src = root / "shared" / "python" / "src"
    for p in (str(root), str(shared_src)):
        if p not in sys.path:
            sys.path.insert(0, p)

    from shared_py.modul_mate_db_gates import assert_m604_table_and_policies
    from shared_py.product_policy import demo_trading_allowed, live_trading_allowed

    print(
        "OK: Migration-604-Datei + migrate.py vorhanden; shared_py "
        f"modul_mate_db_gates importierbar. DB-Pflicht: {requires_db}"
    )
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    tenant_id = (os.environ.get("MODUL_MATE_GATE_TENANT_ID") or "default").strip()

    if not dsn:
        if requires_db:
            print(
                f"Grund: {prof_reason or 'Profil-Regel aktiv (PRODUCTION/APP_ENV)'}",
                flush=True,
            )
            _emit_missing_env_help()
            print(
                "FAIL: Pflicht-Profil, aber kein DATABASE_URL (kein SKIP).",
                flush=True,
            )
            return 1
        print(
            "SKIP: DATABASE_URL nicht gesetzt — kein M604-DB-Test (lokal/dev). "
            "Hinweis: bei PRODUCTION=true, APP_ENV in (production, staging, shadow) "
            "oder SELFCHECK_DATABASE_REQUIRED=1 wuerde derselbe Lauf "
            "**Exit 1** liefern."
        )
        return 0

    # Volle M604-Schema- und (default-)Seed-Pruefung, dann product_policy-Ablesung
    try:
        gates = assert_m604_table_and_policies(
            dsn, tenant_id=tenant_id, connect_timeout_sec=8
        )
    except Exception as exc:  # noqa: BLE001 — CLI
        print("FAIL: M604-Schema/Standard-Policies/DB (shared_py):", exc)
        return 1

    da = demo_trading_allowed(gates)
    la = live_trading_allowed(gates)
    print(
        f"OK: M604 app.tenant_modul_mate_gates tenant_id={tenant_id!r} "
        f"demo_allowed={da} live_allowed={la} (product_policy + DB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
