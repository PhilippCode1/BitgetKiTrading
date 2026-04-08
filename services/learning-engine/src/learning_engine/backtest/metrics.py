from __future__ import annotations

from typing import Any

from learning_engine.analytics.strategy_metrics import compute_trade_metrics


def evaluations_to_rows(evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalisiert DB-Zeilen für compute_trade_metrics."""
    return list(evals)


def backtest_aggregate_metrics(evals: list[dict[str, Any]]) -> dict[str, Any]:
    rows = evaluations_to_rows(evals)
    m = compute_trade_metrics(rows)
    span_ms = 0
    if rows:
        span_ms = max(int(r["closed_ts_ms"]) for r in rows) - min(
            int(r["closed_ts_ms"]) for r in rows
        )
    hours = max(1, span_ms // 3_600_000) if span_ms > 0 else 1
    coverage = min(1.0, len(rows) / max(1, hours) / 5.0)
    out = {
        "trades": m["trades"],
        "win_rate": m["win_rate"],
        "profit_factor": m["profit_factor"],
        "max_drawdown": m["max_drawdown"],
        "avg_pnl_net": None,
        "stop_out_rate": m["stop_out_rate"],
        "gross_profit": m["gross_profit"],
        "gross_loss": m["gross_loss"],
        "fee_drag": m["fee_drag"],
        "funding_drag": m["funding_drag"],
        "take_trade_rate": m["take_trade_rate"],
        "liquidation_risk_rate": m["liquidation_risk_rate"],
        "avg_expected_return_bps": m["avg_expected_return_bps"],
        "avg_expected_return_gross_bps": m["avg_expected_return_gross_bps"],
        "avg_expected_mae_bps": m["avg_expected_mae_bps"],
        "avg_expected_mfe_bps": m["avg_expected_mfe_bps"],
        "coverage": round(coverage, 6),
    }
    if rows:
        from decimal import Decimal

        s = sum(Decimal(str(r.get("pnl_net_usdt", "0"))) for r in rows)
        out["avg_pnl_net"] = float(s / len(rows))
    return out
