#!/usr/bin/env python3
"""Fuehrt einen Billing-Tageslauf aus (siehe Migration 600, COMMERCIAL_ENABLED)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT,
    ROOT / "services" / "api-gateway" / "src",
    ROOT / "shared" / "python" / "src",
):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None, help="Nur dieser tenant_id")
    parser.add_argument("--date", default=None, help="Accrual-Datum UTC YYYY-MM-DD")
    args = parser.parse_args()

    from psycopg.rows import dict_row

    from api_gateway.billing.daily_run import run_daily_billing
    from api_gateway.config import get_gateway_settings
    from api_gateway.db import get_database_url
    from config.gateway_settings import get_gateway_settings as cached_gateway_settings

    cached_gateway_settings.cache_clear()
    settings = get_gateway_settings()
    accrual = date.fromisoformat(args.date) if args.date else None
    dsn = get_database_url()
    if not dsn.strip():
        raise SystemExit("DATABASE_URL fehlt.")
    import psycopg

    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        out = run_daily_billing(
            conn,
            settings=settings,
            accrual_date=accrual,
            tenant_id_filter=args.tenant,
        )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
