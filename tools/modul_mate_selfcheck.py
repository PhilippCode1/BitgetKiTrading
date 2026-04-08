#!/usr/bin/env python3
"""
Self-Check: Modul-Mate-Execution-Gates (Migration 604 + Live-Broker-Policy).

Ohne DATABASE_URL: nur Import- und Dateipruefungen.
Mit DATABASE_URL: Zeile in app.tenant_modul_mate_gates fuer MODUL_MATE_GATE_TENANT_ID
(default default) und Kurz-Auswertung demo/live laut product_policy.

Exit 0 bei Erfolg, 1 bei Fehler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
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

    from shared_py.modul_mate_db_gates import fetch_tenant_modul_mate_gates_from_dsn
    from shared_py.product_policy import demo_trading_allowed, live_trading_allowed

    print(
        "OK: Migration 604 + migrate.py vorhanden, shared_py importierbar "
        "(angewendete/pending Migrationen nur mit DB pruefbar)"
    )

    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    tenant_id = (os.environ.get("MODUL_MATE_GATE_TENANT_ID") or "default").strip()
    if not dsn:
        print("SKIP: DATABASE_URL nicht gesetzt - keine DB-Pruefung")
        return 0

    try:
        gates = fetch_tenant_modul_mate_gates_from_dsn(dsn, tenant_id=tenant_id)
    except Exception as exc:  # noqa: BLE001 — CLI-Selfcheck
        print("FAIL: DB-Verbindung oder Query:", exc)
        return 1

    if gates is None:
        print(
            "FAIL: Kein Eintrag app.tenant_modul_mate_gates "
            f"fuer tenant_id={tenant_id!r}"
        )
        return 1

    da = demo_trading_allowed(gates)
    la = live_trading_allowed(gates)
    print(f"OK: Gates tenant_id={tenant_id!r} " f"demo_allowed={da} live_allowed={la}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
