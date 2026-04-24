from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from paper_broker.storage import repo_position_events, repo_positions
from shared_py.risk_engine import (
    compute_drawdown_from_points,
    compute_margin_usage_pct,
    compute_total_equity,
)

_DAY_MS = 86_400_000
_WEEK_MS = 7 * _DAY_MS


def build_paper_account_risk_metrics(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    tenant_id: str,
    account_row: dict[str, Any],
    now_ms: int,
    projected_margin: Decimal = Decimal("0"),
    projected_fee: Decimal = Decimal("0"),
) -> dict[str, Any]:
    tid = str(tenant_id).strip() or "default"
    open_positions = [
        position
        for position in repo_positions.list_open_positions(conn, tenant_id=tid)
        if str(position.get("account_id") or "") == str(account_id)
        and str(position.get("state") or "").lower() in {"open", "partially_closed"}
    ]
    used_margin = sum(
        (_dec(position.get("isolated_margin")) for position in open_positions),
        Decimal("0"),
    )
    available_equity = _dec(account_row.get("equity"))
    total_equity = compute_total_equity(
        available_equity=available_equity,
        used_margin=used_margin,
    )
    projected_margin = _dec(projected_margin)
    projected_fee = _dec(projected_fee)
    projected_total_equity = max(Decimal("0"), total_equity - projected_fee)
    equity_for_limits = projected_total_equity if projected_fee > 0 else total_equity
    projected_margin_usage_pct = compute_margin_usage_pct(
        total_equity=projected_total_equity,
        used_margin=used_margin + max(Decimal("0"), projected_margin),
    )
    current_margin_usage_pct = compute_margin_usage_pct(
        total_equity=total_equity,
        used_margin=used_margin,
    )

    initial_equity = _dec(account_row.get("initial_equity"))
    all_points = repo_position_events.list_account_equity_points(
        conn,
        account_id=account_id,
        tenant_id=tid,
        limit=5000,
    )
    day_points = repo_position_events.list_account_equity_points(
        conn,
        account_id=account_id,
        tenant_id=tid,
        since_ts_ms=max(0, now_ms - _DAY_MS),
        limit=2000,
    )
    week_points = repo_position_events.list_account_equity_points(
        conn,
        account_id=account_id,
        tenant_id=tid,
        since_ts_ms=max(0, now_ms - _WEEK_MS),
        limit=5000,
    )
    all_drawdown = compute_drawdown_from_points(
        current_equity=equity_for_limits,
        equity_points=[format(initial_equity, "f")] + all_points if initial_equity > 0 else all_points,
    )
    daily_drawdown = compute_drawdown_from_points(
        current_equity=equity_for_limits,
        equity_points=day_points,
    )
    weekly_drawdown = compute_drawdown_from_points(
        current_equity=equity_for_limits,
        equity_points=week_points,
    )
    return {
        "open_positions_count": len(open_positions),
        "used_margin": used_margin,
        "available_equity": available_equity,
        "total_equity": total_equity,
        "projected_total_equity": equity_for_limits,
        "current_margin_usage_pct": current_margin_usage_pct,
        "projected_margin_usage_pct": projected_margin_usage_pct,
        "account_drawdown_pct": all_drawdown["drawdown_pct"],
        "daily_drawdown_pct": daily_drawdown["drawdown_pct"],
        "weekly_drawdown_pct": weekly_drawdown["drawdown_pct"],
        "daily_loss_usdt": _dec(daily_drawdown["loss_usdt"]),
        "all_time_peak_equity": _dec(all_drawdown["peak_equity"]),
        "daily_peak_equity": _dec(daily_drawdown["peak_equity"]),
        "weekly_peak_equity": _dec(weekly_drawdown["peak_equity"]),
    }


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))
