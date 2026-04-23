#!/usr/bin/env python3
"""
Replay-Validation der Apex-Audit-Ledger-Kette (HTTP, interner Service-Key).

Beispiel:
  python scripts/verify_audit_ledger_chain.py --base-url http://127.0.0.1:8098
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

_ROOT = Path(__file__).resolve().parents[1]
_SP = _ROOT / "shared" / "python" / "src"
if _SP.is_dir():
    sys.path.insert(0, str(_SP))

from shared_py.service_auth import INTERNAL_SERVICE_HEADER


def main() -> int:
    p = argparse.ArgumentParser(description="Audit-Ledger Ketten-Verifikation")
    p.add_argument(
        "--base-url",
        default=os.environ.get("AUDIT_LEDGER_BASE_URL", "http://127.0.0.1:8098"),
    )
    p.add_argument(
        "--internal-key",
        default=os.environ.get("INTERNAL_API_KEY", ""),
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    key = (args.internal_key or "").strip()
    if not key:
        print("INTERNAL_API_KEY fehlt (ENV oder --internal-key)", file=sys.stderr)
        return 2
    url = f"{base}/internal/v1/verify-chain"
    headers = {INTERNAL_SERVICE_HEADER: key}
    r = httpx.get(url, headers=headers, timeout=30.0)
    print(r.status_code, r.text)
    if r.status_code != 200:
        return 1
    data = r.json()
    if not data.get("chain_valid"):
        print("Kette UNGUELTIG:", data.get("errors"), file=sys.stderr)
        return 1
    print("Kette OK, Eintraege:", data.get("entries_checked"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
