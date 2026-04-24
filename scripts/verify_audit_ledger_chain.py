#!/usr/bin/env python3
"""
Prueft die letzten N Apex-Audit-Ledger-Eintraege: Hash-Kette (prev -> digest),
Recompute chain_hash, Ed25519 (audit-ledger Service).

  DATABASE_URL=... python scripts/verify_audit_ledger_chain.py
  python scripts/verify_audit_ledger_chain.py --limit 1000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "services" / "audit-ledger" / "src"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from audit_ledger.ledger_repository import LedgerRepository  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Fenstergroesse (Standard 1000)",
    )
    args = ap.parse_args()
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("FAIL: DATABASE_URL fehlt", file=sys.stderr, flush=True)
        return 1

    class _Dsn:
        __slots__ = ("database_url",)

        def __init__(self, u: str) -> None:
            self.database_url = u

    repo = LedgerRepository(_Dsn(dsn))  # type: ignore[arg-type]
    try:
        ok, errors, n, first_bad = repo.verify_chain_last_n(n=args.limit)
    except Exception as exc:  # noqa: BLE001
        print("FAIL: verify_chain_last_n: ", str(exc)[:1_200], file=sys.stderr)
        return 1
    if ok and n == 0:
        print("SUCCESS: keine Eintraege in app.apex_audit_ledger_entries")
        return 0
    if ok:
        print(
            "SUCCESS: Hash-Kette und Signaturen (letzte "
            f"{n} Eintraege) vollstaendig gueltig"
        )
        return 0
    print("ALARM: Kette/Signatur-Integritaet verletzt", file=sys.stderr, flush=True)
    if first_bad is not None:
        print(
            f"  erster bemerkter Index (DB id / PK): {first_bad}",
            file=sys.stderr,
            flush=True,
        )
    for e in errors:
        print(f"  {e}", file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
