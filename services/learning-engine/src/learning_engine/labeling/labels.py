from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from learning_engine.labeling.target_windows import (
    TARGET_EVALUATION_CONTRACT_VERSION,
    clip_candles_to_evaluation_window,
    regime_target_stratification_hints,
)
from learning_engine.storage.repo_context import _parse_jsonb
from shared_py.model_contracts import build_feature_snapshot, build_model_output_snapshot


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def _positive_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        out = Decimal(str(value))
    except Exception:
        return None
    return out if out > 0 else None


@dataclass(frozen=True)
class TradeTargetLabels:
    decision_ts_ms: int
    take_trade_label: bool
    expected_return_bps: Decimal
    expected_return_gross_bps: Decimal
    expected_mae_bps: Decimal
    expected_mfe_bps: Decimal
    liquidation_proximity_bps: Decimal | None
    liquidation_risk: bool
    slippage_bps_entry: Decimal | None
    slippage_bps_exit: Decimal | None


@dataclass(frozen=True)
class TradeTargetComputation:
    """Ergebnis inkl. Audit fuer model_contract_json (Target-Labeling, Prompt 20)."""

    labels: TradeTargetLabels
    audit: dict[str, Any]


def compute_exit_stats(
    fills: list[dict[str, Any]], *, side: str, entry_avg: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (exit_qty, exit_vwap, pnl_gross)."""
    if len(fills) < 2:
        return Decimal("0"), Decimal("0"), Decimal("0")
    exits = fills[1:]
    if not exits:
        return Decimal("0"), Decimal("0"), Decimal("0")
    tq = Decimal("0")
    tp = Decimal("0")
    pnl = Decimal("0")
    s = side.lower()
    for f in exits:
        q = _dec(f["qty_base"])
        p = _dec(f["price"])
        tq += q
        tp += p * q
        if s == "long":
            pnl += (p - entry_avg) * q
        else:
            pnl += (entry_avg - p) * q
    vwap = tp / tq if tq > 0 else Decimal("0")
    return tq, vwap, pnl


def extract_signal_reference_price(sig: dict[str, Any] | None) -> Decimal | None:
    if not sig:
        return None
    raw = _parse_jsonb(sig.get("source_snapshot_json"))
    if not isinstance(raw, dict):
        return None
    return _positive_decimal(raw.get("last_close"))


def candle_close_reference(candle: dict[str, Any] | None) -> Decimal | None:
    if not candle:
        return None
    return _positive_decimal(candle.get("close"))


def compute_trade_targets(
    *,
    side: str,
    state: str,
    decision_ts_ms: int,
    opened_ts_ms: int,
    evaluation_end_ts_ms: int,
    qty_base: Decimal,
    entry_price_avg: Decimal,
    exit_price_avg: Decimal | None,
    pnl_net_usdt: Decimal,
    entry_reference_price: Decimal | None,
    exit_reference_price: Decimal | None,
    path_candles: list[dict[str, Any]],
    isolated_margin: Decimal | None,
    fees_total_usdt: Decimal,
    funding_total_usdt: Decimal,
    maintenance_margin_rate: Decimal,
    liq_fee_buffer_usdt: Decimal,
    market_regime: str | None = None,
    stop_price: Decimal | None = None,
) -> TradeTargetComputation:
    s = side.lower().strip()
    if s not in ("long", "short"):
        raise ValueError(f"unsupported side: {side!r}")

    clipped, window_issues = clip_candles_to_evaluation_window(
        path_candles,
        decision_ts_ms=int(decision_ts_ms),
        evaluation_end_ts_ms=int(evaluation_end_ts_ms),
    )

    qty = abs(qty_base)
    entry_ref = entry_reference_price if entry_reference_price and entry_reference_price > 0 else entry_price_avg
    exit_ref = (
        exit_reference_price
        if exit_reference_price and exit_reference_price > 0
        else (exit_price_avg if exit_price_avg and exit_price_avg > 0 else entry_price_avg)
    )

    notional_ref = qty * entry_ref if qty > 0 and entry_ref > 0 else Decimal("0")
    gross_return_bps = _directional_move_bps(entry_ref, exit_ref, s)
    net_return_bps = (
        pnl_net_usdt / notional_ref * Decimal("10000")
        if notional_ref > 0
        else gross_return_bps
    )

    best_move = gross_return_bps
    worst_move = gross_return_bps
    for candle in clipped:
        for field in ("high", "low"):
            price = _positive_decimal(candle.get(field))
            if price is None:
                continue
            move = _directional_move_bps(entry_ref, price, s)
            if move > best_move:
                best_move = move
            if move < worst_move:
                worst_move = move
    expected_mfe_bps = max(best_move, Decimal("0"))
    expected_mae_bps = max(-worst_move, Decimal("0"))

    liq_price = _approx_liquidation_price(
        isolated_margin=isolated_margin,
        qty=qty,
        entry_avg=entry_price_avg,
        side=s,
        accrued_fees=fees_total_usdt,
        net_funding_ledger=funding_total_usdt,
        maintenance_margin_rate=maintenance_margin_rate,
        liq_fee_buffer_usdt=liq_fee_buffer_usdt,
    )
    liquidation_risk = str(state).lower().strip() == "liquidated"
    liquidation_proximity_bps: Decimal | None = Decimal("0") if liquidation_risk else None
    if not liquidation_risk and liq_price is not None and entry_price_avg > 0:
        post_open = [
            candle for candle in clipped if int(candle.get("start_ts_ms") or 0) >= int(opened_ts_ms)
        ]
        adverse_price = (
            exit_ref if exit_ref > 0 else (exit_price_avg if exit_price_avg and exit_price_avg > 0 else entry_price_avg)
        )
        if s == "long":
            adverse_price = min(entry_price_avg, adverse_price)
            for candle in post_open:
                low = _positive_decimal(candle.get("low"))
                if low is not None and low < adverse_price:
                    adverse_price = low
            cushion_bps = (adverse_price - liq_price) / entry_price_avg * Decimal("10000")
        else:
            adverse_price = max(entry_price_avg, adverse_price)
            for candle in post_open:
                high = _positive_decimal(candle.get("high"))
                if high is not None and high > adverse_price:
                    adverse_price = high
            cushion_bps = (liq_price - adverse_price) / entry_price_avg * Decimal("10000")
        if cushion_bps <= 0:
            liquidation_proximity_bps = Decimal("0")
            liquidation_risk = True
        else:
            liquidation_proximity_bps = cushion_bps

    policy_stop_proximity_bps = _policy_stop_proximity_bps(
        side=s,
        entry_ref=entry_ref,
        opened_ts_ms=int(opened_ts_ms),
        evaluation_end_ts_ms=int(evaluation_end_ts_ms),
        stop_price=stop_price,
        path_candles=clipped,
    )

    labels = TradeTargetLabels(
        decision_ts_ms=int(decision_ts_ms),
        take_trade_label=bool(net_return_bps > 0 and not liquidation_risk),
        expected_return_bps=net_return_bps,
        expected_return_gross_bps=gross_return_bps,
        expected_mae_bps=expected_mae_bps,
        expected_mfe_bps=expected_mfe_bps,
        liquidation_proximity_bps=liquidation_proximity_bps,
        liquidation_risk=liquidation_risk,
        slippage_bps_entry=_adverse_slippage_bps(entry_ref, entry_price_avg, side=s, leg="entry"),
        slippage_bps_exit=_adverse_slippage_bps(
            exit_ref,
            exit_price_avg if exit_price_avg is not None else exit_ref,
            side=s,
            leg="exit",
        ),
    )

    audit: dict[str, Any] = {
        "target_evaluation_contract_version": TARGET_EVALUATION_CONTRACT_VERSION,
        "evaluation_window": {
            "decision_ts_ms": int(decision_ts_ms),
            "opened_ts_ms": int(opened_ts_ms),
            "evaluation_end_ts_ms": int(evaluation_end_ts_ms),
            "aggregation": "1m_path_primary_else_signal_tf",
            "candles_in_window": len(clipped),
            "candles_input": len(path_candles),
        },
        "reference_leg": {
            "entry_reference": "signal_last_close_or_candle_close_before_decision",
            "exit_reference": "last_candle_close_in_window_or_before_closed_ts",
            "excursion_anchor": "entry_reference_price_for_mae_mfe",
            "net_return_notional": "qty_abs_times_entry_reference",
        },
        "cost_assumptions": {
            "net_return_bps": "pnl_net_includes_fees_funding_and_slippage_vs_reference",
            "gross_return_bps": "mark_to_market_reference_to_reference_excludes_cost_model_detail",
        },
        "trade_side": s,
        "window_issues": window_issues,
        "regime_stratification": regime_target_stratification_hints(market_regime),
        "risk_proximity": {
            "liquidation_proximity_bps": str(liquidation_proximity_bps)
            if liquidation_proximity_bps is not None
            else None,
            "policy_stop_proximity_bps": str(policy_stop_proximity_bps)
            if policy_stop_proximity_bps is not None
            else None,
        },
    }
    return TradeTargetComputation(labels=labels, audit=audit)


def parse_stop_plan(meta_or_row: dict[str, Any]) -> dict[str, Any] | None:
    raw = meta_or_row.get("stop_plan_json")
    p = _parse_jsonb(raw)
    return p if isinstance(p, dict) else None


def timing_from_events(
    events: list[dict[str, Any]], *, opened_ts_ms: int
) -> tuple[bool, bool, bool, bool, int | None, int | None]:
    """stop_hit, tp1,tp2,tp3, time_to_tp1, time_to_stop."""
    tp1 = tp2 = tp3 = False
    stop_hit = False
    t_tp1: int | None = None
    t_stop: int | None = None
    for ev in events:
        t = int(ev["ts_ms"])
        typ = str(ev["type"])
        det = _parse_jsonb(ev.get("details")) or {}
        if typ == "TP_HIT":
            idx = det.get("tp_index")
            try:
                i = int(idx)
            except (TypeError, ValueError):
                continue
            if i == 0:
                tp1 = True
                if t_tp1 is None:
                    t_tp1 = t - opened_ts_ms
            elif i == 1:
                tp2 = True
            elif i == 2:
                tp3 = True
        elif typ in ("SL_HIT", "RUNNER_TRAIL_HIT"):
            stop_hit = True
            if t_stop is None:
                t_stop = t - opened_ts_ms
    return stop_hit, tp1, tp2, tp3, t_tp1, t_stop


def signal_snapshot_compact(sig: dict[str, Any] | None) -> dict[str, Any]:
    return build_model_output_snapshot(sig)


def feature_snapshot_compact(
    *,
    primary_timeframe: str,
    primary_feature: dict[str, Any] | None,
    features_by_tf: dict[str, dict[str, Any] | None],
    quality_issues: list[str] | None = None,
) -> dict[str, Any]:
    return build_feature_snapshot(
        primary_timeframe=primary_timeframe,
        primary_feature=primary_feature,
        features_by_tf=features_by_tf,
        quality_issues=quality_issues,
    )


def structure_snapshot_compact(
    state: dict[str, Any] | None, events: list[dict[str, Any]]
) -> dict[str, Any]:
    out: dict[str, Any] = {"state": state, "recent_events": []}
    if state:
        out["trend_dir"] = state.get("trend_dir")
        out["compression_flag"] = state.get("compression_flag")
    for e in events[:10]:
        out["recent_events"].append(
            {
                "type": e.get("type"),
                "ts_ms": e.get("ts_ms"),
                "details": e.get("details_json"),
            }
        )
    return out


def _directional_move_bps(reference: Decimal, price: Decimal, side: str) -> Decimal:
    if reference <= 0:
        return Decimal("0")
    if side == "long":
        return (price - reference) / reference * Decimal("10000")
    return (reference - price) / reference * Decimal("10000")


def _adverse_slippage_bps(
    reference: Decimal,
    fill_price: Decimal,
    *,
    side: str,
    leg: str,
) -> Decimal | None:
    if reference <= 0 or fill_price <= 0:
        return None
    if leg == "entry":
        diff = fill_price - reference if side == "long" else reference - fill_price
    elif leg == "exit":
        diff = reference - fill_price if side == "long" else fill_price - reference
    else:
        raise ValueError(f"unsupported leg: {leg!r}")
    if diff <= 0:
        return Decimal("0")
    return diff / reference * Decimal("10000")


def _policy_stop_proximity_bps(
    *,
    side: str,
    entry_ref: Decimal,
    opened_ts_ms: int,
    evaluation_end_ts_ms: int,
    stop_price: Decimal | None,
    path_candles: list[dict[str, Any]],
) -> Decimal | None:
    """
    Puffer zwischen schlimmster adverser Pfad-Extremstelle und geplantem Stop (Policy-Risiko).
    None wenn kein Stop bekannt; 0 wenn Stufe erreicht oder durchbrochen.
    """
    if stop_price is None or stop_price <= 0 or entry_ref <= 0:
        return None
    post_open = [
        c
        for c in path_candles
        if opened_ts_ms <= int(c.get("start_ts_ms") or 0) <= evaluation_end_ts_ms
    ]
    if not post_open:
        return None
    if side == "long":
        adverse: Decimal | None = None
        for candle in post_open:
            low = _positive_decimal(candle.get("low"))
            if low is None:
                continue
            adverse = low if adverse is None else min(adverse, low)
        if adverse is None:
            return None
        cushion = adverse - stop_price
        if cushion <= 0:
            return Decimal("0")
        return cushion / entry_ref * Decimal("10000")
    adverse_h: Decimal | None = None
    for candle in post_open:
        high = _positive_decimal(candle.get("high"))
        if high is None:
            continue
        adverse_h = high if adverse_h is None else max(adverse_h, high)
    if adverse_h is None:
        return None
    cushion = stop_price - adverse_h
    if cushion <= 0:
        return Decimal("0")
    return cushion / entry_ref * Decimal("10000")


def _approx_liquidation_price(
    *,
    isolated_margin: Decimal | None,
    qty: Decimal,
    entry_avg: Decimal,
    side: str,
    accrued_fees: Decimal,
    net_funding_ledger: Decimal,
    maintenance_margin_rate: Decimal,
    liq_fee_buffer_usdt: Decimal,
) -> Decimal | None:
    if (
        isolated_margin is None
        or isolated_margin <= 0
        or qty <= 0
        or entry_avg <= 0
        or maintenance_margin_rate < 0
    ):
        return None
    if side == "long":
        denom = qty * (Decimal("1") - maintenance_margin_rate)
        if denom <= 0:
            return None
        px = (
            entry_avg * qty
            + accrued_fees
            - net_funding_ledger
            + liq_fee_buffer_usdt
            - isolated_margin
        ) / denom
        return px if px > 0 else None
    if side == "short":
        denom = qty * (Decimal("1") + maintenance_margin_rate)
        if denom <= 0:
            return None
        px = (
            isolated_margin
            + entry_avg * qty
            - accrued_fees
            + net_funding_ledger
            - liq_fee_buffer_usdt
        ) / denom
        return px if px > 0 else None
    return None
