#!/usr/bin/env python3
"""
Prueft Repo-Layout fuer kanonische vs. Demo-Migrationen (ohne Datenbank).

Exit 0: postgres_demo/*.sql vorhanden; Platzhalter-Migrationen 596/597/603 verweisen auf den Vertrag.
Exit 1: Abweichung.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    demo_dir = root / "infra" / "migrations" / "postgres_demo"
    if not demo_dir.is_dir():
        print("FAIL: infra/migrations/postgres_demo fehlt", file=sys.stderr, flush=True)
        return 1
    demos = sorted(demo_dir.glob("*.sql"))
    if len(demos) < 3:
        print(
            f"FAIL: postgres_demo erwartet mindestens 3 .sql, gefunden {len(demos)}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    for name in (
        "596_local_demo_freshness_seed.sql",
        "597_local_demo_ticker_drawings.sql",
        "603_local_demo_learning_registry_seed.sql",
    ):
        p = root / "infra" / "migrations" / "postgres" / name
        if not p.is_file():
            print(f"FAIL: fehlt {p.relative_to(root)}", file=sys.stderr, flush=True)
            return 1
        text = p.read_text(encoding="utf-8")
        if "SELECT 1" not in text:
            print(
                f"FAIL: {name} muss No-Op SELECT 1 enthalten (Forward-only Platzhalter)",
                file=sys.stderr,
                flush=True,
            )
            return 1
        if "postgres_demo" not in text:
            print(
                f"FAIL: {name} muss auf postgres_demo verweisen",
                file=sys.stderr,
                flush=True,
            )
            return 1
    print(
        f"check_migration_demo_layout: OK ({len(demos)} demo-sql, Platzhalter 596/597/603)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
