from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared_py.playbook_registry import (
    preferred_strategy_for_playbook,
    preferred_strategy_for_playbook_family,
)


CLASS_TO_STRATEGY_NAME: dict[str, str] = {
    "mikro": "MeanReversionMicroStrategy",
    "gross": "BreakoutBoxStrategy",
    "kern": "TrendContinuationStrategy",
}


def infer_strategy_name(row: dict[str, Any]) -> str:
    snap = row.get("signal_snapshot_json") or {}
    if isinstance(snap, str):
        import json

        try:
            snap = json.loads(snap)
        except json.JSONDecodeError:
            snap = {}
    if not isinstance(snap, dict):
        snap = {}
    raw = snap.get("strategy_name") or snap.get("strategy")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    playbook_id = snap.get("playbook_id")
    strategy_from_playbook = preferred_strategy_for_playbook(
        str(playbook_id).strip() if playbook_id is not None else None
    )
    if strategy_from_playbook:
        return strategy_from_playbook
    playbook_family = snap.get("playbook_family")
    strategy_from_family = preferred_strategy_for_playbook_family(
        str(playbook_family).strip() if playbook_family is not None else None
    )
    if strategy_from_family:
        return strategy_from_family
    source_snapshot = snap.get("source_snapshot_json") or {}
    if isinstance(source_snapshot, dict):
        playbook_ctx = source_snapshot.get("playbook_context") or {}
        if isinstance(playbook_ctx, dict):
            strategy_from_ctx = preferred_strategy_for_playbook(
                str(playbook_ctx.get("selected_playbook_id") or "").strip() or None
            ) or preferred_strategy_for_playbook_family(
                str(playbook_ctx.get("selected_playbook_family") or "").strip() or None
            )
            if strategy_from_ctx:
                return strategy_from_ctx
    cls = str(snap.get("signal_class", "kern")).lower()
    return CLASS_TO_STRATEGY_NAME.get(cls, CLASS_TO_STRATEGY_NAME["kern"])


def _dec(x: Any) -> Decimal:
    if x is None:
        return Decimal("0")
    return Decimal(str(x))


def _avg_decimal(rows: list[dict[str, Any]], field: str) -> float:
    values = [Decimal(str(r[field])) for r in rows if r.get(field) is not None]
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def max_drawdown_fraction_from_pnls(pnls: list[Decimal]) -> float:
    """Max Drawdown relativ zum laufenden Peak der Equity-Kurve (Start 0)."""
    if not pnls:
        return 0.0
    peak = Decimal("0")
    max_dd = Decimal("0")
    eq = Decimal("0")
    for p in pnls:
        eq += p
        if eq > peak:
            peak = eq
        if peak > Decimal("1e-12"):
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def compute_trade_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Health-Metriken für eine Liste von trade_evaluations (bereits gefiltert)."""
    n = len(rows)
    if n == 0:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": None,
            "max_drawdown": 0.0,
            "stop_out_rate": 0.0,
            "fee_drag": 0.0,
            "funding_drag": 0.0,
            "wins": 0,
            "losses": 0,
            "take_trade_rate": 0.0,
            "liquidation_risk_rate": 0.0,
            "avg_expected_return_bps": 0.0,
            "avg_expected_return_gross_bps": 0.0,
            "avg_expected_mae_bps": 0.0,
            "avg_expected_mfe_bps": 0.0,
        }

    wins = sum(1 for r in rows if bool(r.get("direction_correct")))
    take_trade = sum(1 for r in rows if bool(r.get("take_trade_label")))
    liquidation_risk = sum(1 for r in rows if bool(r.get("liquidation_risk")))
    gross_profit = Decimal("0")
    gross_loss = Decimal("0")
    fees_sum = Decimal("0")
    funding_sum = Decimal("0")
    stop_hits = 0
    ordered_pnls: list[Decimal] = []

    for r in sorted(
        rows,
        key=lambda x: (int(x["closed_ts_ms"]), str(x.get("evaluation_id") or "")),
    ):
        pnl = _dec(r.get("pnl_net_usdt"))
        ordered_pnls.append(pnl)
        fees_sum += _dec(r.get("fees_total_usdt"))
        funding_sum += _dec(r.get("funding_total_usdt"))
        if bool(r.get("stop_hit")):
            stop_hits += 1
        if pnl > 0:
            gross_profit += pnl
        elif pnl < 0:
            gross_loss += pnl

    win_rate = wins / n if n else 0.0
    gl_abs = abs(float(gross_loss))
    gp_f = float(gross_profit)
    if gl_abs > 1e-12:
        profit_factor = gp_f / gl_abs
    else:
        profit_factor = None if gp_f <= 0 else float("inf")

    mdd = max_drawdown_fraction_from_pnls(ordered_pnls)

    denom = gp_f + gl_abs
    if denom > 1e-12:
        fee_drag = float(fees_sum) / denom
        funding_drag = float(funding_sum) / denom
    else:
        fee_drag = 0.0
        funding_drag = 0.0

    return {
        "trades": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": win_rate,
        "gross_profit": gp_f,
        "gross_loss": float(gross_loss),
        "profit_factor": profit_factor,
        "max_drawdown": mdd,
        "stop_out_rate": stop_hits / n if n else 0.0,
        "fee_drag": fee_drag,
        "funding_drag": funding_drag,
        "take_trade_rate": take_trade / n if n else 0.0,
        "liquidation_risk_rate": liquidation_risk / n if n else 0.0,
        "avg_expected_return_bps": _avg_decimal(rows, "expected_return_bps"),
        "avg_expected_return_gross_bps": _avg_decimal(rows, "expected_return_gross_bps"),
        "avg_expected_mae_bps": _avg_decimal(rows, "expected_mae_bps"),
        "avg_expected_mfe_bps": _avg_decimal(rows, "expected_mfe_bps"),
    }
