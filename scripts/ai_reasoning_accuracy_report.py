#!/usr/bin/env python3
"""
DoD Prompt 70: Report zu Reasoning Accuracy
(letzte N Trades aus learn.post_trade_review).

Voraussetzung: Migration 627, Learning-Engine hat post_trade_review-Zeilen geschrieben.

  python scripts/ai_reasoning_accuracy_report.py
  python scripts/ai_reasoning_accuracy_report.py --limit 10 --dsn $DATABASE_URL
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any


def _dsn_fingerprint(dsn: str) -> str:
    return sha256(dsn.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _json_out_path(
    out: str, dsn: str, limit: int, acc_vals: list[float], mean_acc: float | None
) -> Path:
    payload = {
        "status": "ok",
        "dsn_fingerprint": _dsn_fingerprint(dsn),
        "limit": limit,
        "rows": len(acc_vals) if acc_vals is not None else 0,
        "mean_reasoning_accuracy_0_1": None if mean_acc is None else round(mean_acc, 4),
    }
    if acc_vals:
        payload["min_reasoning_accuracy_0_1"] = round(min(acc_vals), 4)
        payload["max_reasoning_accuracy_0_1"] = round(max(acc_vals), 4)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return p


@contextmanager
def _connect(dsn: str) -> Iterator[Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("psycopg erforderlich: pip install psycopg[binary]") from exc
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        yield conn


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Reasoning-Accuracy-Report (learn.post_trade_review)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Anzahl letzter Zeilen (default: 10)",
    )
    ap.add_argument(
        "--dsn", type=str, default="", help="Postgres-DSN (sonst env DATABASE_URL)"
    )
    ap.add_argument(
        "--json-out",
        type=str,
        default="",
        help="Metriken als JSON schreiben (Dossier P70/P85)",
    )
    args = ap.parse_args()
    dsn = (args.dsn or os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        print("Fehlend: DATABASE_URL oder --dsn", file=sys.stderr)
        return 2
    lim = max(1, min(100, int(args.limit)))

    sql = """
    SELECT
        review_id,
        created_ts,
        quality_label,
        reasoning_accuracy_0_1,
        pnl_net_usdt,
        thesis_holds,
        side,
        signal_id,
        window_start_ts_ms,
        window_end_ts_ms
    FROM learn.post_trade_review
    ORDER BY created_ts DESC
    LIMIT %s
    """
    with _connect(dsn) as conn:
        try:
            rows = conn.execute(sql, (lim,)).fetchall()
        except Exception as exc:
            print(
                f"Tabelle learn.post_trade_review fehlt oder unlesbar: {exc}",
                file=sys.stderr,
            )
            return 2

    if not rows:
        print("Keine Eintraege in learn.post_trade_review.")
        if args.json_out:
            p = Path(args.json_out)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(
                    {
                        "status": "empty",
                        "dsn_fingerprint": _dsn_fingerprint(dsn),
                        "limit": lim,
                        "rows": 0,
                        "mean_reasoning_accuracy_0_1": None,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        return 0

    acc_vals = [float(r["reasoning_accuracy_0_1"]) for r in rows]
    mean_acc = statistics.fmean(acc_vals) if acc_vals else 0.0

    print("=== AI Reasoning Accuracy (letzte Trades) ===\n")
    print(f"Trades (n): {len(rows)}")
    print(f"Metrik: reasoning_accuracy_0_1 (Mittelwert): {mean_acc:.3f}\n")
    print(
        f"{'label':<22} {'acc':>6} {'pnl':>10} {'thesis':>7} "
        f"{'side':>6} {'signal_id'}"
    )
    print("-" * 95)
    for r in rows:
        th = r["thesis_holds"]
        ths = "n/a" if th is None else ("ja" if th else "nein")
        print(
            f"{str(r['quality_label']):<22} "
            f"{float(r['reasoning_accuracy_0_1']):6.2f} "
            f"{float(r['pnl_net_usdt']):10.4f} "
            f"{ths:>7} "
            f"{str(r['side'] or ''):>6} "
            f"{r['signal_id']}"
        )
    print()
    if args.json_out:
        _json_out_path(args.json_out, dsn, lim, acc_vals, mean_acc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
