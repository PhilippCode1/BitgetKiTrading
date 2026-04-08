"""Vergleichsmetriken: Abstention, FP, Stop-Failures, Slippage-Proxy, Kapital-Effizienz."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from learning_engine.analytics.strategy_metrics import compute_trade_metrics, max_drawdown_fraction_from_pnls
from shared_py.model_contracts import extract_primary_feature_snapshot


def _actual_take_label(row: dict[str, Any]) -> int:
    return 1 if bool(row.get("take_trade_label")) else 0


def _system_take_proxy(row: dict[str, Any]) -> int:
    """Proxy: System hat 'trade' intent wenn Label gesetzt (Trainingsziel = ex-post Take)."""
    return _actual_take_label(row)


def _error_labels(row: dict[str, Any]) -> list[str]:
    raw = row.get("error_labels_json")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            o = json.loads(raw)
            return [str(x) for x in o] if isinstance(o, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _pnl_dec(row: dict[str, Any]) -> Decimal:
    try:
        return Decimal(str(row.get("pnl_net_usdt") or "0"))
    except Exception:
        return Decimal("0")


def _exec_cost_bps(row: dict[str, Any]) -> float | None:
    raw = row.get("feature_snapshot_json")
    if not isinstance(raw, dict):
        return None
    p = extract_primary_feature_snapshot(raw)
    if not isinstance(p, dict):
        return None
    v = p.get("execution_cost_bps")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def take_decision_metrics(
    rows: list[dict[str, Any]],
    pred_take: list[int],
    *,
    name: str,
) -> dict[str, Any]:
    n = len(rows)
    if n != len(pred_take) or n == 0:
        return {"name": name, "error": "length_mismatch_or_empty", "n": n}

    y = [_actual_take_label(r) for r in rows]
    abstain = [p == 0 for p in pred_take]
    ab_n = sum(abstain)
    ab_correct = sum(1 for i in range(n) if abstain[i] and y[i] == 0)
    abstention_precision_neg = float(ab_correct / ab_n) if ab_n else None

    hi = [p == 1 for p in pred_take]
    hi_n = sum(hi)
    hi_fp = sum(1 for i in range(n) if hi[i] and y[i] == 0)
    high_conf_fp_rate = float(hi_fp / hi_n) if hi_n else None

    agreement = sum(1 for i in range(n) if pred_take[i] == y[i]) / n

    stop_fail = 0
    traded_n = 0
    for i, r in enumerate(rows):
        if pred_take[i] != 1:
            continue
        traded_n += 1
        labs = _error_labels(r)
        if any("stop" in x.lower() or "slip" in x.lower() for x in labs):
            stop_fail += 1

    sub_rows = [rows[i] for i in range(n) if pred_take[i] == 1]
    sub_m = compute_trade_metrics(sub_rows) if sub_rows else compute_trade_metrics([])

    pnls = [_pnl_dec(r) for i, r in enumerate(rows) if pred_take[i] == 1]
    mdd_sub = max_drawdown_fraction_from_pnls(pnls) if pnls else 0.0

    costs: list[float] = []
    pnls_for_corr: list[float] = []
    for i, r in enumerate(rows):
        if pred_take[i] != 1:
            continue
        c = _exec_cost_bps(r)
        if c is not None:
            costs.append(c)
            pnls_for_corr.append(float(_pnl_dec(r)))

    slip_corr = _pearson(costs, pnls_for_corr) if len(costs) >= 8 else None

    return {
        "name": name,
        "n": n,
        "abstention_count": ab_n,
        "abstention_precision_on_no_take_label": abstention_precision_neg,
        "pred_take_count": hi_n,
        "high_conf_false_positive_rate_vs_take_label": high_conf_fp_rate,
        "agreement_rate_with_take_trade_label": round(agreement, 6),
        "stop_related_error_labels_when_pred_trade": stop_fail,
        "trades_when_pred_trade": traded_n,
        "subset_when_pred_trade": {
            "trades": sub_m["trades"],
            "win_rate": sub_m["win_rate"],
            "profit_factor": sub_m["profit_factor"],
            "max_drawdown_equity_curve": mdd_sub,
            "stop_out_rate": sub_m["stop_out_rate"],
            "avg_pnl_net_usdt": float(sum(pnls) / len(pnls)) if pnls else None,
        },
        "slippage_sensitivity_pearson_pnl_vs_execution_cost_bps": slip_corr,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx <= 0 or dy <= 0:
        return None
    return float(num / (dx * dy))


def aggregate_system_trade_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return compute_trade_metrics(rows)
