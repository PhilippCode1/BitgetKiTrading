"""Prompt 20: Performance- und Export-Endpunkte auf customer_router haengen."""

from __future__ import annotations

import csv
import io
import time
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fpdf import FPDF
from psycopg.rows import dict_row

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_read
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_customer_performance import (
    build_demo_paper_performance,
    fetch_live_tenant_finance_snapshot,
)
from api_gateway.routes_commerce_customer import (
    _ensure_commercial,
    _mask_tenant_id,
    _require_tenant_commercial_state,
    _resolve_target_tenant,
)


def attach_customer_performance_routes(router: APIRouter) -> None:
    @router.get(
        "/performance",
        summary="Performance: Demo (Paper) und mandantenbezogene Live-/Gebuehr-KPIs",
    )
    def customer_performance_get(
        request: Request,
        auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
        trades_limit: int = Query(default=120, ge=10, le=500),
        symbol: str | None = Query(default=None, max_length=32),
    ) -> dict[str, Any]:
        settings = get_gateway_settings()
        _ensure_commercial(settings)
        tid = _resolve_target_tenant(auth, None)
        now_ms = int(time.time() * 1000)
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            demo = build_demo_paper_performance(
                conn,
                trades_limit=trades_limit,
                ledger_limit=60,
                equity_max_points=800,
                symbol=symbol.strip().upper() if symbol and symbol.strip() else None,
                now_ms=now_ms,
            )
            live_fin: dict[str, Any] | None = None
            if settings.profit_fee_module_enabled:
                try:
                    live_fin = fetch_live_tenant_finance_snapshot(conn, tenant_id=tid)
                except Exception:
                    live_fin = {
                        "scope": "tenant_commercial",
                        "high_water_mark_cents": None,
                        "recent_statements": [],
                        "error": "profit_fee_unavailable",
                    }
            else:
                live_fin = {
                    "scope": "tenant_commercial",
                    "module_disabled": True,
                    "notice": {
                        "de": "Gewinnbeteiligungs-/HWM-Modul ist aus. Live-Fills siehe Konsole Live-Broker.",
                        "en": "Profit-fee / HWM module is off. See live broker console for fills.",
                    },
                }
        record_gateway_audit_line(
            request, auth, "commerce_customer_performance_read", extra={"tenant_id": tid}
        )
        return {
            "schema_version": "commerce-customer-performance-v1",
            "tenant_id_masked": _mask_tenant_id(tid),
            "generated_at_ms": now_ms,
            "explainability": {
                "de": (
                    "KI-Erklaerungen zu einzelnen Signalen finden Sie unter Signale → Detail → "
                    "Erklaerung. Es handelt sich um nachvollziehbare Modellhinweise, keine Prognose."
                ),
                "en": (
                    "Per-signal AI explanations: Signals → detail → explain. "
                    "These are model rationales, not forecasts."
                ),
            },
            "demo": demo,
            "live_and_fees": live_fin,
        }

    @router.get(
        "/performance/export",
        summary="Performance-Export (CSV)",
    )
    def customer_performance_export_csv(
        request: Request,
        auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
        format: Literal["csv"] = Query(default="csv"),
        trades_limit: int = Query(default=200, ge=10, le=500),
    ) -> Response:
        if format != "csv":
            raise HTTPException(status_code=400, detail="only csv supported")
        settings = get_gateway_settings()
        _ensure_commercial(settings)
        tid = _resolve_target_tenant(auth, None)
        now_ms = int(time.time() * 1000)
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            demo = build_demo_paper_performance(
                conn,
                trades_limit=trades_limit,
                ledger_limit=40,
                equity_max_points=400,
                symbol=None,
                now_ms=now_ms,
            )
        trades = demo.get("closed_trades_recent") or []
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "position_id",
                "symbol",
                "side",
                "closed_ts_ms",
                "pnl_net_usdt",
                "fees_total_usdt",
                "funding_total_usdt",
                "state",
            ]
        )
        for row in trades:
            w.writerow(
                [
                    row.get("position_id"),
                    row.get("symbol"),
                    row.get("side"),
                    row.get("closed_ts_ms"),
                    row.get("pnl_net_usdt"),
                    row.get("fees_total_usdt"),
                    row.get("funding_total_usdt"),
                    row.get("state"),
                ]
            )
        record_gateway_audit_line(
            request,
            auth,
            "commerce_customer_performance_export_csv",
            extra={"tenant_id": tid, "rows": len(trades)},
        )
        body = "\ufeff" + buf.getvalue()
        return Response(
            content=body.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="demo-performance-trades.csv"',
            },
        )

    @router.get(
        "/performance/report.pdf",
        summary="Kurzbericht Demo-Performance (PDF)",
    )
    def customer_performance_report_pdf(
        request: Request,
        auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
        trades_limit: int = Query(default=120, ge=10, le=300),
    ) -> Response:
        settings = get_gateway_settings()
        _ensure_commercial(settings)
        tid = _resolve_target_tenant(auth, None)
        now_ms = int(time.time() * 1000)
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            demo = build_demo_paper_performance(
                conn,
                trades_limit=trades_limit,
                ledger_limit=30,
                equity_max_points=400,
                symbol=None,
                now_ms=now_ms,
            )
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, "Demo performance summary (shared paper)", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(
            0,
            5,
            "Shared simulator — not isolated per account. "
            "Figures explain mechanics; they are not a promise of results.",
            ln=True,
        )
        pdf.ln(2)
        acc = demo.get("account") or {}
        periods = demo.get("periods") or {}
        dd = demo.get("drawdown") or {}
        streaks = demo.get("streaks") or {}
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Account", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"Equity: {acc.get('equity', 'n/a')}  Initial: {acc.get('initial_equity', 'n/a')}", ln=True)
        pdf.cell(0, 5, f"Fees total (paper fee ledger): {demo.get('fees_total_usdt')}", ln=True)
        pdf.cell(0, 5, f"Funding total: {demo.get('funding_total_usdt')}", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Periods (closed trades in export window)", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for label, key in (("7d", "last_7d"), ("30d", "last_30d"), ("window", "all_in_window")):
            p = periods.get(key) or {}
            pdf.cell(
                0,
                5,
                f"{label}: trades={p.get('trade_count')} win_rate={p.get('win_rate')} "
                f"sum_pnl={p.get('sum_pnl_net_usdt')} pf={p.get('profit_factor')}",
                ln=True,
            )
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Drawdown / streaks", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"Max DD % (equity curve): {dd.get('max_drawdown_pct')}", ln=True)
        pdf.cell(
            0,
            5,
            f"Max win streak: {streaks.get('max_consecutive_wins')} "
            f"Max loss streak: {streaks.get('max_consecutive_losses')}",
            ln=True,
        )
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"Open positions: {demo.get('open_positions_count')}", ln=True)
        record_gateway_audit_line(
            request,
            auth,
            "commerce_customer_performance_export_pdf",
            extra={"tenant_id": tid},
        )
        raw = pdf.output(dest="S")
        if isinstance(raw, (bytes, bytearray)):
            content = bytes(raw)
        elif isinstance(raw, str):
            content = raw.encode("latin-1")
        else:
            content = bytes(raw)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="demo-performance-summary.pdf"',
            },
        )
