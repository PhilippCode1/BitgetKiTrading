"""Kunden-Performance (Prompt 20): Demo-Paper-Kennzahlen, Perioden, Streaks, Drawdown."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from api_gateway.db_dashboard_queries import (
    fetch_equity_series,
    fetch_paper_metrics_summary,
    fetch_paper_open_positions,
    fetch_paper_trades_recent,
)
from api_gateway.db_paper_mutations import resolve_primary_paper_account_id
from api_gateway.db_paper_reads import fetch_paper_account_ledger_recent


def _f(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def compute_max_drawdown_pct(equity_series: list[float]) -> dict[str, float]:
    """Gibt maximale Drawdown-Tiefe in Prozent relativ zum laufenden Peak (<= 0)."""
    if not equity_series:
        return {"max_drawdown_pct": 0.0, "peak_equity": 0.0, "trough_equity": 0.0}
    peak = equity_series[0]
    max_dd = 0.0
    trough = peak
    for eq in equity_series:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (eq - peak) / peak * 100.0
            if dd < max_dd:
                max_dd = dd
                trough = eq
    return {
        "max_drawdown_pct": round(max_dd, 4),
        "peak_equity": float(peak),
        "trough_equity": float(trough),
    }


def compute_streaks(pnls_chronological: list[float]) -> dict[str, Any]:
    """pnls in Zeit-Reihenfolge (aelteste zuerst); laengste Sieg-/Verlustserien."""
    max_w = max_l = run_w = run_l = 0
    cur_kind: str | None = None
    cur_len = 0
    for p in pnls_chronological:
        if p > 0:
            run_w += 1
            run_l = 0
            max_w = max(max_w, run_w)
            cur_kind = "win"
            cur_len = run_w
        elif p < 0:
            run_l += 1
            run_w = 0
            max_l = max(max_l, run_l)
            cur_kind = "loss"
            cur_len = run_l
        else:
            run_w = run_l = 0
            cur_kind = None
            cur_len = 0
    return {
        "max_consecutive_wins": max_w,
        "max_consecutive_losses": max_l,
        "current_streak": {"kind": cur_kind, "length": cur_len},
    }


def summarize_closed_trades(
    trades: list[dict[str, Any]], *, cutoff_ms: int | None
) -> dict[str, Any]:
    """Filtert geschlossene Trades mit PnL; cutoff_ms=None = alles."""
    rows: list[dict[str, Any]] = []
    for t in trades:
        ts = t.get("closed_ts_ms")
        pnl = t.get("pnl_net_usdt")
        if ts is None or pnl is None:
            continue
        if cutoff_ms is not None and int(ts) < cutoff_ms:
            continue
        rows.append(t)
    pnls = [_f(r.get("pnl_net_usdt")) for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    sum_win = sum(wins)
    sum_loss_abs = sum(abs(p) for p in losses)
    profit_factor = (sum_win / sum_loss_abs) if sum_loss_abs > 0 else None
    return {
        "trade_count": len(rows),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": (len(wins) / len(pnls)) if pnls else None,
        "sum_pnl_net_usdt": round(sum(pnls), 6),
        "avg_win_usdt": round(sum_win / len(wins), 6) if wins else None,
        "avg_loss_usdt": round(-sum_loss_abs / len(losses), 6) if losses else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "fees_sum_usdt": round(
            sum(_f(r.get("fees_total_usdt")) for r in rows if r.get("fees_total_usdt") is not None),
            6,
        ),
    }


def build_demo_paper_performance(
    conn: psycopg.Connection[Any],
    *,
    trades_limit: int,
    ledger_limit: int,
    equity_max_points: int,
    symbol: str | None,
    now_ms: int,
) -> dict[str, Any]:
    lim = max(1, min(500, trades_limit))
    open_pos = fetch_paper_open_positions(conn, symbol=symbol)
    trades = fetch_paper_trades_recent(conn, symbol=symbol, limit=lim)
    metrics = fetch_paper_metrics_summary(conn)
    eq_series_raw = fetch_equity_series(conn, max_points=max(10, min(2000, equity_max_points)))
    equities = [float(p["equity"]) for p in eq_series_raw]
    dd = compute_max_drawdown_pct(equities)

    closed_chrono = sorted(
        [
            t
            for t in trades
            if t.get("closed_ts_ms") is not None and t.get("pnl_net_usdt") is not None
        ],
        key=lambda x: int(x["closed_ts_ms"]),
    )
    pnls_chrono = [_f(t.get("pnl_net_usdt")) for t in closed_chrono]
    streaks = compute_streaks(pnls_chrono)

    d7 = now_ms - 7 * 86400000
    d30 = now_ms - 30 * 86400000
    periods = {
        "last_7d": summarize_closed_trades(trades, cutoff_ms=d7),
        "last_30d": summarize_closed_trades(trades, cutoff_ms=d30),
        "all_in_window": summarize_closed_trades(trades, cutoff_ms=None),
    }

    ledger_snippet: list[dict[str, Any]] = []
    aid = resolve_primary_paper_account_id(conn)
    if aid is not None:
        ledger_snippet = fetch_paper_account_ledger_recent(
            conn, account_id=aid, limit=max(1, min(80, ledger_limit))
        )

    unrealized_total = sum(_f(p.get("unrealized_pnl_usdt")) for p in open_pos)

    return {
        "scope": "shared_paper_environment",
        "scope_notice": {
            "de": (
                "Demo-Kennzahlen stammen aus dem gemeinsamen Paper-Simulator (nicht isoliert "
                "pro Mandant). Sie dienen dem Verstaendnis von Ablauf, Gebuehren und PnL-Logik — "
                "nicht als persoenliche Garantie."
            ),
            "en": (
                "Demo metrics come from the shared paper simulator (not isolated per tenant). "
                "They explain fees and PnL mechanics — not a personal guarantee."
            ),
        },
        "open_positions": open_pos,
        "open_positions_count": len(open_pos),
        "unrealized_pnl_usdt_sum": round(unrealized_total, 6),
        "closed_trades_recent": trades,
        "account": metrics.get("account"),
        "fees_total_usdt": metrics.get("fees_total_usdt"),
        "funding_total_usdt": metrics.get("funding_total_usdt"),
        "equity_curve": eq_series_raw,
        "drawdown": dd,
        "streaks": streaks,
        "periods": periods,
        "account_ledger_recent": ledger_snippet,
    }


def fetch_live_tenant_finance_snapshot(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any]:
    """Mandantenbezogene Live-/Gebuehr-Kennzichen (Profit-Fee-Modul)."""
    from api_gateway.db_profit_fee import fetch_hwm_cents, list_statements_for_tenant

    out: dict[str, Any] = {
        "scope": "tenant_commercial",
        "high_water_mark_cents": None,
        "recent_statements": [],
    }
    try:
        out["high_water_mark_cents"] = {
            "paper": fetch_hwm_cents(conn, tenant_id=tenant_id, trading_mode="paper"),
            "live": fetch_hwm_cents(conn, tenant_id=tenant_id, trading_mode="live"),
        }
    except psycopg.errors.UndefinedTable:
        out["high_water_mark_cents"] = None
    except psycopg.Error:
        out["high_water_mark_cents"] = None
    try:
        out["recent_statements"] = list_statements_for_tenant(
            conn, tenant_id=tenant_id, limit=12, include_draft=False
        )
    except psycopg.errors.UndefinedTable:
        out["recent_statements"] = []
    except psycopg.Error:
        out["recent_statements"] = []
    return out


def fetch_admin_performance_aggregates(
    conn: psycopg.Connection[Any], *, now_ms: int
) -> dict[str, Any]:
    """Aggregierte Plattform-Kennzahlen (ohne Mandanten-PII)."""
    d30 = now_ms - 30 * 86400000
    paper_open = 0
    paper_closed_30d = 0
    paper_pnl_sum_30d: Decimal = Decimal("0")
    paper_closed_all = 0
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)::bigint AS c
            FROM paper.positions
            WHERE state IN ('open', 'partially_closed')
            """
        ).fetchone()
        paper_open = int(dict(row or {})["c"] or 0)
    except psycopg.errors.UndefinedTable:
        pass
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)::bigint AS c
            FROM paper.positions
            WHERE state IN ('closed', 'liquidated')
            """
        ).fetchone()
        paper_closed_all = int(dict(row or {})["c"] or 0)
    except psycopg.errors.UndefinedTable:
        pass
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)::bigint AS c,
                   COALESCE(SUM(e.pnl_net_usdt), 0) AS pnl
            FROM paper.positions p
            LEFT JOIN learn.trade_evaluations e ON e.paper_trade_id = p.position_id
            WHERE p.state IN ('closed', 'liquidated')
              AND p.closed_ts_ms IS NOT NULL
              AND p.closed_ts_ms >= %s
            """,
            (d30,),
        ).fetchone()
        if row:
            d = dict(row)
            paper_closed_30d = int(d["c"] or 0)
            paper_pnl_sum_30d = Decimal(str(d["pnl"] or 0))
    except psycopg.errors.UndefinedTable:
        pass
    except psycopg.Error:
        pass

    live_fills_30d = 0
    live_orders_open = 0
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)::bigint AS c FROM live.fills
            WHERE exchange_ts_ms >= %s
            """,
            (d30,),
        ).fetchone()
        live_fills_30d = int(dict(row or {})["c"] or 0)
    except psycopg.errors.UndefinedTable:
        pass
    except psycopg.Error:
        pass
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)::bigint AS c FROM live.orders
            WHERE status NOT IN (
                'filled', 'canceled', 'cancelled', 'error', 'replaced',
                'flattened', 'flatten_failed', 'timed_out'
            )
            """
        ).fetchone()
        live_orders_open = int(dict(row or {})["c"] or 0)
    except psycopg.errors.UndefinedTable:
        pass
    except psycopg.Error:
        pass

    return {
        "schema_version": "admin-performance-overview-v1",
        "as_of_ms": now_ms,
        "paper": {
            "open_positions": paper_open,
            "closed_trades_total": paper_closed_all,
            "closed_trades_last_30d": paper_closed_30d,
            "sum_realized_pnl_net_usdt_30d": float(paper_pnl_sum_30d),
        },
        "live": {
            "fills_last_30d": live_fills_30d,
            "orders_non_terminal_count": live_orders_open,
            "note_de": (
                "Live-Zaehler sind plattformweit; feinere Mandanten-Zuordnung folgt mit "
                "Ausfuehrungs-Metadaten."
            ),
        },
    }
