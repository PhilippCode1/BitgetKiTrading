#!/usr/bin/env python3
"""
DB-Auszug: Golden Record + is_verified fuer execution_id (Prompt 68 / DoD).

  DATABASE_URL=... python scripts/apex_trade_forensic_export.py <execution_id>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
for p in (
    _root,
    _root / "shared" / "python" / "src",
    _root / "services" / "audit-ledger" / "src",
):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/apex_trade_forensic_export.py <execution_id>", file=sys.stderr)
        return 2
    eid = sys.argv[1].strip()
    dsn = (os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL") or "").strip()
    if not dsn:
        print("DATABASE_URL fehlt", file=sys.stderr)
        return 1

    import psycopg
    from psycopg.rows import dict_row

    from shared_py.observability.apex_trade_forensic_store import (
        expected_previous_chain_for_row,
        fetch_apex_trade_forensic_row,
        verify_row_integrity,
    )

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = fetch_apex_trade_forensic_row(conn, execution_id=eid)
    if not row:
        print(json.dumps({"ok": False, "error": "kein Eintrag in app.apex_trade_forensics"}))
        return 3
    with psycopg.connect(dsn) as conn2:
        try:
            rid = int(row["id"])
        except (TypeError, KeyError, ValueError):
            rid = 0
        expect = expected_previous_chain_for_row(conn2, row_id=rid) if rid else None
        v = verify_row_integrity(row, expected_prev_link=expect)
    pr, ch = row.get("prev_chain_checksum"), row.get("chain_checksum")
    if isinstance(pr, memoryview):
        pr = pr.tobytes()
    if isinstance(ch, memoryview):
        ch = ch.tobytes()
    out = {
        "ok": True,
        "execution_id": row.get("execution_id"),
        "signal_id": row.get("signal_id"),
        "created_at": row.get("created_at"),
        "golden_record": row.get("golden_record"),
        "prev_chain_checksum_hex": pr.hex() if isinstance(pr, bytes) else None,
        "chain_checksum_hex": ch.hex() if isinstance(ch, bytes) else None,
        "is_verified": v.get("is_verified"),
        "verification": v,
    }
    print(json.dumps(out, default=str, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
