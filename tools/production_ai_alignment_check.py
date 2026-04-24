#!/usr/bin/env python3
"""
Produktions-Ausrichtung: ai_evaluation_logs (Operator-Explain) vs. P&L
(learn.trade_evaluations, E2E-Pfad source_signal_id).

Voraussetzung: Postgres-DSN mit live.* und learn.* (meist DATABASE_URL).

  python tools/production_ai_alignment_check.py
  python tools/production_ai_alignment_check.py --hours 24 --output-md report.md

Umgebung: DATABASE_URL
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@contextmanager
def _connect(dsn: str) -> Iterator[Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("psycopg wird benoetigt: pip install psycopg[binary]") from exc
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        yield conn


def _md_cell(s: str) -> str:
    return s.replace("\n", " ").replace("|", "\\|").strip() or "—"


def _fmt_ts(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, datetime):
        s = v.astimezone(UTC)
        return s.isoformat()
    return str(v)


def _to_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AI-Bewertungen (24h) vs. realer P&L, Markdown-Report",
    )
    ap.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Fenster rueckwaerts ab jetzt (default: 24)",
    )
    ap.add_argument(
        "--output-md",
        type=str,
        default="",
        help="Optional: Markdown in Datei schreiben; sonst nur stdout",
    )
    ap.add_argument(
        "--dsn",
        type=str,
        default="",
        help="Postgres-DSN (sonst env DATABASE_URL)",
    )
    args = ap.parse_args()
    dsn = (args.dsn or os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        print("Fehlend: DATABASE_URL oder --dsn", file=sys.stderr)
        return 2
    if args.hours <= 0 or args.hours > 24 * 365:
        print("hours muss 0 < hours <= 8760 sein", file=sys.stderr)
        return 2

    end = datetime.now(UTC)
    start = end - timedelta(hours=float(args.hours))
    berlin = ZoneInfo("Europe/Berlin")

    sql = """
    SELECT
        l.log_id,
        l.created_ts AS eval_ts_utc,
        l.execution_id,
        l.ai_warned,
        l.orchestrator_status,
        d.symbol,
        d.source_signal_id,
        d.created_ts AS decision_ts_utc,
        te.pnl_net_usdt,
        te.closed_ts_ms
    FROM public.ai_evaluation_logs l
    INNER JOIN live.execution_decisions d
        ON d.execution_id = l.execution_id
    LEFT JOIN learn.e2e_decision_records e2e
        ON d.source_signal_id IS NOT NULL
        AND d.source_signal_id ~ '^[0-9a-fA-F-]{36}$'
        AND e2e.signal_id = d.source_signal_id::uuid
    LEFT JOIN learn.trade_evaluations te
        ON te.evaluation_id = e2e.trade_evaluation_id
    WHERE l.task_type = 'operator_explain'
      AND l.created_ts >= %s
      AND l.created_ts < %s
    ORDER BY l.created_ts ASC;
    """

    lines: list[str] = []
    lines.append("# KI- vs. Markt-Ausrichtung (Operator Explain)")
    lines.append("")
    _local = end.astimezone(berlin).strftime("%Y-%m-%d %H:%M %Z")
    lines.append(
        f"Zeitfenster (UTC): `{start.isoformat()}` bis `{end.isoformat()}` — "
        f"**{args.hours} h**; lokal: **{_local}**"
    )
    lines.append("")

    rows_out: list[dict[str, Any]] = []
    with _connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end))
            desc = cur.description or ()
            colnames = [c.name for c in desc]
            for tup in cur.fetchall():
                rows_out.append(dict(zip(colnames, tup, strict=True)))

    if not rows_out:
        lines.append(
            "Keine `ai_evaluation_logs` im Fenster (Join mit `execution_decisions`)."
        )
        lines.append("")

    prec_hits = 0
    loss_denom = 0

    lines.append("## Eintraege im Fenster (operator_explain + execution_id)")
    lines.append("")
    lines.append(
        "| execution_id | symbol | KI-Eval (UTC) | `ai_warned` | P&L (net) | "
        "Verlust? | Warnung vor Realized-Close? |"
    )
    lines.append("|---|---|---|---|---|:---:|---|")

    for r in rows_out:
        pnl = _to_float(r.get("pnl_net_usdt"))
        cts = r.get("closed_ts_ms")
        eval_ts: datetime | None = r.get("eval_ts_utc")
        loss = pnl is not None and pnl < 0
        warned = bool(r.get("ai_warned"))
        before_close: bool | None = None
        if cts is not None and eval_ts is not None:
            close_utc = datetime.fromtimestamp(int(cts) / 1000.0, tz=UTC)
            before_close = eval_ts < close_utc
        if loss and cts is not None and eval_ts is not None:
            loss_denom += 1
            if warned and before_close is True:
                prec_hits += 1
        _pna = "n/a (kein E2E-Eval / trade_evaluation)"
        pnl_s = f"{pnl:.6f}" if pnl is not None else _pna
        loss_s = "ja" if loss else "nein" if pnl is not None else "n/a"
        bcs = (
            "ja" if before_close is True
            else "nein" if before_close is False
            else "n/a (kein closed_ts_ms / kein P&L-Pfad)"
        )
        eid = str(r.get("execution_id") or "")
        lines.append(
            f"| `{_md_cell(eid)}` | {_md_cell(str(r.get('symbol') or ''))} | "
            f"{_md_cell(_fmt_ts(eval_ts))} | {warned!s} | {_md_cell(pnl_s)} | "
            f"{loss_s} | {_md_cell(bcs)} |"
        )
    lines.append("")

    ai_precision: float | None
    if loss_denom == 0:
        ai_precision = None
    else:
        ai_precision = prec_hits / float(loss_denom)

    lines.append("## Kennzahlen")
    lines.append("")
    if ai_precision is None:
        ap_s = "n/a (kein Verlust-Trade im Fenster mit bekannter Close-Zeit)"
    else:
        ap_s = f"**{prec_hits} / {loss_denom}** = **{100.0 * ai_precision:.1f} %**"
    lines.append(
        "**AI Precision** (Def.: bei realisierten *Verlust*-Trades — "
        "Warnheuristik in `ai_warned` und KI-Log *vor* `closed_ts_ms` "
        f"der abschließenden Trade-Evaluation): {ap_s}."
    )
    lines.append("")
    lines.append(
        "_Hinweis: P&L kommt aus `learn.trade_evaluations` ueber "
        "`source_signal_id` → `learn.e2e_decision_records`. Wenn leer, "
        "ist der Lern-Pfad im Fenster evtl. noch nicht geschrieben._"
    )
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.output_md:
        Path(args.output_md).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
