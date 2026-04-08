from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

EXIT_POLICY_VERSION = "shared-exit-v2"

# Einheitlicher Bewertungspfad (evaluate_exit_plan / run_unified_exit_evaluation)
EXIT_EVALUATION_ORDER_DE: tuple[str, ...] = (
    "0. Emergency-Flatten (Plan-Flag force_emergency_close)",
    "1. Time-Stop (Ablauf deadline_ts_ms)",
    "2. Stop-Loss (mark/fill gemaess trigger_type)",
    "3. Trailing / Runner (armed, trail_stop vs Trigger-Preis)",
    "4. Teilgewinne (TP-Stufen, reduce_only)",
    "5. Break-Even-Stop-Anhebung nach TP",
    "6. Trailing-State-Update (High/Low-Water)",
)
_TP_LADDER_FRACTIONS = (
    Decimal("8") / Decimal("30"),
    Decimal("16") / Decimal("30"),
    Decimal("1"),
)


def _dec(value: Any, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _copy_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return deepcopy(plan)


def parse_plan_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return deepcopy(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def merge_plan_override(
    base_stop: dict[str, Any],
    base_tp: dict[str, Any],
    override_stop: dict[str, Any] | None,
    override_tp: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stop_plan = deepcopy(base_stop)
    tp_plan = deepcopy(base_tp)
    if override_stop:
        stop_plan.update({key: value for key, value in override_stop.items() if value is not None})
    if override_tp:
        for key, value in override_tp.items():
            if value is None:
                continue
            if key == "targets" and isinstance(value, list):
                tp_plan["targets"] = deepcopy(value)
                continue
            if key == "runner" and isinstance(value, dict):
                tp_plan["runner"] = {**(tp_plan.get("runner") or {}), **deepcopy(value)}
                continue
            if key == "break_even" and isinstance(value, dict):
                tp_plan["break_even"] = {**(tp_plan.get("break_even") or {}), **deepcopy(value)}
                continue
            tp_plan[key] = value
    return stop_plan, tp_plan


def pick_trigger_price(trigger_type: str, mark: Decimal, fill: Decimal) -> Decimal:
    return mark if str(trigger_type or "fill_price") == "mark_price" else fill


def _side_multiplier(side: str) -> Decimal:
    return Decimal("1") if str(side).lower() == "long" else Decimal("-1")


def _side_close_order(side: str) -> str:
    return "sell" if str(side).lower() == "long" else "buy"


def _ensure_execution_defaults(plan: dict[str, Any]) -> dict[str, Any]:
    execution = dict(plan.get("execution") or {})
    execution.setdefault("reduce_only", True)
    execution.setdefault("order_type", "market")
    execution.setdefault("timing", "immediate")
    execution.setdefault("cancel_replace_behavior", "cancel_existing_reduce_only_then_submit")
    execution.setdefault("estimated_fee_bps", "0")
    execution.setdefault("estimated_slippage_bps", "0")
    plan["execution"] = execution
    plan.setdefault("policy_version", EXIT_POLICY_VERSION)
    return plan


def build_execution_context(
    *,
    estimated_fee_bps: Decimal | None = None,
    estimated_slippage_bps: Decimal | None = None,
    cancel_replace_behavior: str = "cancel_existing_reduce_only_then_submit",
) -> dict[str, Any]:
    return {
        "reduce_only": True,
        "order_type": "market",
        "timing": "immediate",
        "estimated_fee_bps": str(estimated_fee_bps or Decimal("0")),
        "estimated_slippage_bps": str(estimated_slippage_bps or Decimal("0")),
        "cancel_replace_behavior": cancel_replace_behavior,
    }


def approximate_isolated_liquidation_price(
    *,
    side: str,
    entry_price: Decimal,
    leverage: Decimal,
    maintenance_margin_rate: Decimal = Decimal("0.0004"),
) -> Decimal | None:
    """
    Grobe isolierte Linear-Approximation (USDT-Marge), nur fuer Puffer-Checks.
    Kein Ersatz fuer Exchange-Liquidationspreis.
    """
    if entry_price <= 0 or leverage <= 0:
        return None
    inv_l = Decimal("1") / leverage
    mm = maintenance_margin_rate
    sn = str(side).lower()
    if sn == "long":
        return entry_price * (Decimal("1") - inv_l + mm)
    if sn == "short":
        return entry_price * (Decimal("1") + inv_l - mm)
    return None


def leverage_indexed_stop_budget_bps(
    leverage: Decimal,
    *,
    loose_budget_bps: Decimal = Decimal("100"),
    tight_budget_bps: Decimal = Decimal("10"),
    min_leverage: Decimal = Decimal("7"),
    max_leverage: Decimal = Decimal("75"),
) -> Decimal | None:
    """
    7x -> max. 100bps (1.0%), Richtung 75x -> 10bps (0.10%).
    Exponentielle Interpolation, damit hohe Hebel progressiv enger werden.
    """
    if leverage <= 0:
        return None
    if leverage <= min_leverage:
        return loose_budget_bps
    if leverage >= max_leverage:
        return tight_budget_bps
    ratio = float((leverage - min_leverage) / (max_leverage - min_leverage))
    start = float(loose_budget_bps)
    end = float(tight_budget_bps)
    budget = start * ((end / start) ** ratio)
    return Decimal(str(round(budget, 6)))


def executable_stop_floor_bps(
    *,
    market_family: str | None,
    spread_bps: Decimal | None,
    tick_size_bps: Decimal | None,
    volatility_bps: Decimal | None,
    depth_ratio: float | None,
    liquidation_buffer_bps: Decimal | None,
) -> dict[str, Decimal]:
    family = str(market_family or "futures").strip().lower()
    spread_mult = Decimal("3.0") if family in {"spot", "margin"} else Decimal("2.5")
    spread_floor = max(Decimal("0"), (spread_bps or Decimal("0")) * spread_mult)
    tick_floor = max(Decimal("0"), (tick_size_bps or Decimal("0")) * Decimal("2.0"))
    volatility_floor = max(
        Decimal("0"),
        (volatility_bps or Decimal("0"))
        * (Decimal("0.30") if family in {"spot", "margin"} else Decimal("0.22")),
    )
    liquidation_floor = Decimal("0")
    depth_penalty = Decimal("0")
    if depth_ratio is not None:
        if depth_ratio < 0.35:
            depth_penalty = Decimal("15")
        elif depth_ratio < 0.55:
            depth_penalty = Decimal("8")
    executable_floor = max(
        spread_floor,
        tick_floor,
        volatility_floor,
        liquidation_floor,
        depth_penalty,
    )
    return {
        "spread_floor_bps": spread_floor,
        "tick_floor_bps": tick_floor,
        "volatility_floor_bps": volatility_floor,
        "liquidation_floor_bps": liquidation_floor,
        "depth_penalty_bps": depth_penalty,
        "executable_floor_bps": executable_floor,
    }


def adjust_stop_take_for_mae_mfe(
    *,
    side: str,
    entry_price: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    expected_mae_bps: float | None,
    expected_mfe_bps: float | None,
    regime: str | None,
    spread_bps: float | None,
    depth_ratio: float | None,
    mae_safety_mult: float = 1.12,
    mfe_trim_mult: float = 0.92,
    regime_choppy_mae_extra: float = 1.08,
) -> tuple[Decimal | None, Decimal | None, dict[str, Any]]:
    """
    Verschiebt Stop/TP konservativ anhand erwarteter MAE/MFE und Mikrostruktur.
    """
    meta: dict[str, Any] = {
        "inputs": {
            "expected_mae_bps": expected_mae_bps,
            "expected_mfe_bps": expected_mfe_bps,
            "regime": regime,
            "spread_bps": spread_bps,
            "depth_ratio": depth_ratio,
        },
        "adjustments": [],
    }
    if entry_price <= 0:
        return stop_loss, take_profit, meta

    sn = str(side).lower()
    mae = float(expected_mae_bps) if expected_mae_bps is not None else None
    mfe = float(expected_mfe_bps) if expected_mfe_bps is not None else None
    reg = str(regime or "").strip().lower()
    if reg in {"choppy", "range", "volatile", "shock"}:
        mae = (mae or 0.0) * regime_choppy_mae_extra
        meta["adjustments"].append("regime_widen_mae")

    spread_penalty = max(0.0, (spread_bps or 0.0) * 0.15)
    depth_penalty = 0.0
    if depth_ratio is not None and depth_ratio < 0.55:
        depth_penalty = 8.0
        meta["adjustments"].append("low_depth_widen_stop")

    extra_bps = spread_penalty + depth_penalty
    if mae is not None and mae > 0 and stop_loss is not None and stop_loss > 0:
        min_dist_frac = Decimal(str((mae * mae_safety_mult + extra_bps) / 10000.0))
        min_abs = entry_price * min_dist_frac
        if sn == "long":
            if entry_price - stop_loss < min_abs:
                stop_loss = entry_price - min_abs
                meta["adjustments"].append("stop_widened_for_mae")
        else:
            if stop_loss - entry_price < min_abs:
                stop_loss = entry_price + min_abs
                meta["adjustments"].append("stop_widened_for_mae")

    if mfe is not None and mfe > 0 and take_profit is not None and take_profit > 0:
        trim_frac = Decimal(str((mfe * (1.0 - mfe_trim_mult)) / 10000.0))
        trim_abs = entry_price * trim_frac
        if sn == "long":
            if take_profit - entry_price > trim_abs:
                take_profit = take_profit - trim_abs
                meta["adjustments"].append("tp_trimmed_for_mfe_conservatism")
        else:
            if entry_price - take_profit > trim_abs:
                take_profit = take_profit + trim_abs
                meta["adjustments"].append("tp_trimmed_for_mfe_conservatism")

    return stop_loss, take_profit, meta


def build_exit_intent_document(
    *,
    side: str,
    entry_price: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    adjustment_meta: dict[str, Any] | None,
    expected_mae_bps: float | None,
    expected_mfe_bps: float | None,
    market_regime: str | None,
) -> dict[str, Any]:
    """Fuer Qualitaetsanalyse: geplante Exit-Absicht (vor Ausfuehrung)."""
    return {
        "policy_version": EXIT_POLICY_VERSION,
        "evaluation_order_de": list(EXIT_EVALUATION_ORDER_DE),
        "side": side,
        "entry_price": str(entry_price),
        "stop_loss": str(stop_loss) if stop_loss is not None else None,
        "take_profit": str(take_profit) if take_profit is not None else None,
        "expected_mae_bps": expected_mae_bps,
        "expected_mfe_bps": expected_mfe_bps,
        "market_regime": market_regime,
        "projection_adjustment": adjustment_meta or {},
    }


def append_exit_execution_log(plan_record: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Haengt eine tatsaechliche Exit-Ausfuehrung an context_json.execution_log_json an."""
    ctx = dict(plan_record.get("context_json") or {})
    log = list(ctx.get("execution_log_json") or [])
    log.append(entry)
    ctx["execution_log_json"] = log
    return {**plan_record, "context_json": ctx}


_PROFILE_TP_WEIGHTS: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "flatten_fast": (Decimal("0.55"), Decimal("0.30"), Decimal("0.15")),
    "runner_heavy": (Decimal("0.22"), Decimal("0.28"), Decimal("0.50")),
    "early_scale": (Decimal("0.42"), Decimal("0.33"), Decimal("0.25")),
    "liquidity_skim": (Decimal("0.38"), Decimal("0.37"), Decimal("0.25")),
    "funding_skew": (Decimal("0.30"), Decimal("0.35"), Decimal("0.35")),
    "time_biased": (Decimal("0.50"), Decimal("0.35"), Decimal("0.15")),
    "balanced": (Decimal("1"), Decimal("1"), Decimal("1")),
}


def merge_exit_build_overrides(
    *,
    take_pcts: tuple[Decimal, Decimal, Decimal],
    runner_enabled: bool,
    runner_trail_mult: Decimal,
    break_even_after_tp_index: int,
    hints: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Gleiche Semantik fuer Live/Paper: deterministische Anpassung der Exit-Plan-Parameter aus
    `execution_hints` (Signal-Resolver), ohne die einheitliche Exit-Bewertungskette zu aendern.
    """
    out_take = take_pcts
    out_runner = runner_enabled
    out_be = int(break_even_after_tp_index)
    out_mult = runner_trail_mult
    out_arm_idx = 1
    if not isinstance(hints, dict) or not hints:
        return {
            "take_pcts": out_take,
            "runner_enabled": out_runner,
            "runner_trail_mult": out_mult,
            "break_even_after_tp_index": out_be,
            "runner_arm_after_tp_index": out_arm_idx,
        }
    profile = str(hints.get("take_pct_profile") or "balanced").strip() or "balanced"
    weights = _PROFILE_TP_WEIGHTS.get(profile, _PROFILE_TP_WEIGHTS["balanced"])
    if profile != "balanced":
        total_in = sum(take_pcts)
        wsum = weights[0] + weights[1] + weights[2]
        if wsum > 0 and total_in > 0:
            out_take = (
                total_in * weights[0] / wsum,
                total_in * weights[1] / wsum,
                total_in * weights[2] / wsum,
            )
    if hints.get("runner_enabled") is not None:
        out_runner = bool(hints.get("runner_enabled"))
    ridx = hints.get("runner_arm_after_tp_index")
    if ridx is not None:
        try:
            out_arm_idx = int(ridx)
        except (TypeError, ValueError):
            out_arm_idx = 1
        if not 0 <= out_arm_idx <= 2:
            out_arm_idx = 1
    bidx = hints.get("break_even_after_tp_index")
    if bidx is not None:
        try:
            bi = int(bidx)
        except (TypeError, ValueError):
            bi = out_be
        if 0 <= bi <= 2:
            out_be = bi
    return {
        "take_pcts": out_take,
        "runner_enabled": out_runner,
        "runner_trail_mult": out_mult,
        "break_even_after_tp_index": out_be,
        "runner_arm_after_tp_index": out_arm_idx,
    }


def derive_tp_targets_from_final_target(
    *,
    side: str,
    entry_price: Decimal,
    final_target_price: Decimal,
    take_pcts: tuple[Decimal, Decimal, Decimal],
    trigger_type: str,
) -> list[dict[str, Any]]:
    distance = abs(final_target_price - entry_price)
    sign = _side_multiplier(side)
    targets: list[dict[str, Any]] = []
    for index, fraction in enumerate(_TP_LADDER_FRACTIONS):
        target_price = entry_price + sign * distance * fraction
        targets.append(
            {
                "index": index,
                "target_price": str(target_price),
                "take_pct": str(take_pcts[index]),
                "order_type": "market",
                "trigger_type": trigger_type,
                "runner": index == 2,
            }
        )
    return targets


def build_live_exit_plans(
    *,
    side: str,
    entry_price: Decimal,
    initial_qty: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    stop_trigger_type: str,
    tp_trigger_type: str,
    take_pcts: tuple[Decimal, Decimal, Decimal],
    runner_enabled: bool,
    runner_trail_mult: Decimal,
    break_even_after_tp_index: int,
    estimated_fee_bps: Decimal | None = None,
    estimated_slippage_bps: Decimal | None = None,
    timeframe: str | None = None,
    time_stop_deadline_ts_ms: int | None = None,
    runner_arm_after_tp_index: int = 1,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    execution = build_execution_context(
        estimated_fee_bps=estimated_fee_bps,
        estimated_slippage_bps=estimated_slippage_bps,
    )
    stop_plan = None
    if stop_loss is not None and stop_loss > 0:
        stop_plan = {
            "policy_version": EXIT_POLICY_VERSION,
            "trigger_type": stop_trigger_type,
            "stop_price": str(stop_loss),
            "execution": deepcopy(execution),
            "quality": {"stop_quality_score": None, "risk_warnings": []},
        }
    tp_plan = None
    if take_profit is not None and take_profit > 0 and entry_price > 0:
        final_distance = abs(take_profit - entry_price)
        trail_offset = (final_distance / Decimal("3")) * runner_trail_mult if final_distance > 0 else Decimal("0")
        arm_idx = int(runner_arm_after_tp_index)
        if arm_idx < 0 or arm_idx > 2:
            arm_idx = 1
        tp_plan = {
            "policy_version": EXIT_POLICY_VERSION,
            "timeframe": timeframe,
            "trigger_type": tp_trigger_type,
            "execution": deepcopy(execution),
            "targets": derive_tp_targets_from_final_target(
                side=side,
                entry_price=entry_price,
                final_target_price=take_profit,
                take_pcts=take_pcts,
                trigger_type=tp_trigger_type,
            ),
            "runner": {
                "enabled": bool(runner_enabled),
                "mode": "fixed_offset",
                "trail_atr_mult": str(runner_trail_mult),
                "trail_offset": str(trail_offset),
                "arm_after_tp2": arm_idx >= 2,
                "arm_after_tp_index": arm_idx,
                "armed": False,
                "high_water": None,
                "low_water": None,
                "trail_stop": None,
            },
            "break_even": {
                "enabled": True,
                "trigger_after_tp_index": int(break_even_after_tp_index),
                "applied": False,
            },
            "execution_state": {
                "hit_tp_indices": [],
                "initial_qty": str(initial_qty),
            },
        }
    unified_meta = {
        "pipeline_version": EXIT_POLICY_VERSION,
        "evaluation_order_de": list(EXIT_EVALUATION_ORDER_DE),
    }
    if stop_plan is not None:
        stop_plan["unified_exit"] = unified_meta
    if tp_plan is not None:
        tp_plan["unified_exit"] = unified_meta
    if time_stop_deadline_ts_ms is not None and int(time_stop_deadline_ts_ms) > 0:
        ts = {
            "enabled": True,
            "deadline_ts_ms": int(time_stop_deadline_ts_ms),
            "fired": False,
        }
        if stop_plan is not None:
            stop_plan["time_stop"] = ts
        elif tp_plan is not None:
            tp_plan["time_stop"] = ts
    return stop_plan, tp_plan


def eval_stop_tp_full(
    *,
    side: str,
    mark: Decimal,
    fill: Decimal,
    stop_plan: dict[str, Any] | None,
    tp_plan: dict[str, Any] | None,
    already_hit_tp: set[int],
) -> tuple[bool, list[int]]:
    stop_px = None
    stop_trigger_type = "mark_price"
    if stop_plan:
        stop_trigger_type = str(stop_plan.get("trigger_type") or "mark_price")
        stop_px = _dec(stop_plan.get("stop_price"))
        if stop_px <= 0:
            stop_px = None
    stop_trigger = pick_trigger_price(stop_trigger_type, mark, fill)
    hit_stop = False
    if stop_px is not None:
        if str(side).lower() == "long" and stop_trigger <= stop_px:
            hit_stop = True
        if str(side).lower() == "short" and stop_trigger >= stop_px:
            hit_stop = True

    hit_tp: list[int] = []
    tp_default = "fill_price"
    if tp_plan:
        tp_default = str(tp_plan.get("trigger_type") or "fill_price")
    for index, row in enumerate((tp_plan or {}).get("targets") or []):
        if index in already_hit_tp:
            continue
        target_price = _dec(row.get("target_price"))
        if target_price <= 0:
            continue
        trigger_type = str(row.get("trigger_type") or tp_default)
        trigger_price = pick_trigger_price(trigger_type, mark, fill)
        if str(side).lower() == "long" and trigger_price >= target_price:
            hit_tp.append(index)
        if str(side).lower() == "short" and trigger_price <= target_price:
            hit_tp.append(index)
    return hit_stop, hit_tp


def update_runner_state(
    *,
    side: str,
    fill_price: Decimal,
    runner: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    state = dict(runner)
    trail_offset = _dec(state.get("trail_offset"))
    if trail_offset <= 0:
        return state, False
    changed = False
    if str(side).lower() == "long":
        high_water = max(_dec(state.get("high_water"), default=str(fill_price)), fill_price)
        if str(high_water) != str(state.get("high_water")):
            changed = True
        state["high_water"] = str(high_water)
        trail_stop = high_water - trail_offset
        if str(trail_stop) != str(state.get("trail_stop")):
            changed = True
        state["trail_stop"] = str(trail_stop)
    else:
        low_water = min(_dec(state.get("low_water"), default=str(fill_price)), fill_price)
        if str(low_water) != str(state.get("low_water")):
            changed = True
        state["low_water"] = str(low_water)
        trail_stop = low_water + trail_offset
        if str(trail_stop) != str(state.get("trail_stop")):
            changed = True
        state["trail_stop"] = str(trail_stop)
    return state, changed


def runner_trail_hit(
    *,
    side: str,
    mark: Decimal,
    fill: Decimal,
    tp_plan: dict[str, Any] | None,
    trigger_default: str,
) -> bool:
    runner = dict((tp_plan or {}).get("runner") or {})
    if not runner.get("armed"):
        return False
    trail_stop = _dec(runner.get("trail_stop"))
    if trail_stop <= 0:
        return False
    trigger_type = str(runner.get("trigger_type") or trigger_default)
    trigger_price = pick_trigger_price(trigger_type, mark, fill)
    if str(side).lower() == "long":
        return trigger_price <= trail_stop
    return trigger_price >= trail_stop


def apply_break_even_update(
    *,
    side: str,
    entry_price: Decimal,
    stop_plan: dict[str, Any] | None,
    tp_plan: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, bool]:
    if stop_plan is None or tp_plan is None:
        return stop_plan, tp_plan, False
    break_even = dict(tp_plan.get("break_even") or {})
    if not break_even.get("enabled", True):
        return stop_plan, tp_plan, False
    if break_even.get("applied"):
        return stop_plan, tp_plan, False
    trigger_after = int(break_even.get("trigger_after_tp_index") or 0)
    hits = {int(item) for item in ((tp_plan.get("execution_state") or {}).get("hit_tp_indices") or [])}
    if trigger_after not in hits:
        return stop_plan, tp_plan, False
    next_stop = _copy_plan(stop_plan)
    if next_stop is None:
        return stop_plan, tp_plan, False
    current_stop = _dec(next_stop.get("stop_price"))
    if current_stop <= 0 or entry_price <= 0:
        return stop_plan, tp_plan, False
    if str(side).lower() == "long":
        updated_stop = max(current_stop, entry_price)
    else:
        updated_stop = min(current_stop, entry_price)
    if updated_stop == current_stop:
        next_tp = _copy_plan(tp_plan)
        if next_tp is None:
            return next_stop, tp_plan, False
        next_tp["break_even"] = {**break_even, "applied": True}
        return next_stop, next_tp, False
    next_stop["stop_price"] = str(updated_stop)
    next_tp = _copy_plan(tp_plan)
    if next_tp is None:
        return next_stop, tp_plan, True
    next_tp["break_even"] = {**break_even, "applied": True}
    return next_stop, next_tp, True


def _take_pct(target: dict[str, Any]) -> Decimal:
    take_pct = _dec(target.get("take_pct"))
    if take_pct <= 0:
        return Decimal("0")
    return take_pct


def _price_relation_valid(*, side: str, entry_price: Decimal, stop_price: Decimal | None, target_prices: list[Decimal]) -> list[str]:
    reasons: list[str] = []
    side_norm = str(side).lower()
    if entry_price <= 0:
        reasons.append("exit_entry_price_invalid")
        return reasons
    if stop_price is not None and stop_price > 0:
        if side_norm == "long" and stop_price >= entry_price:
            reasons.append("stop_loss_not_below_entry")
        if side_norm == "short" and stop_price <= entry_price:
            reasons.append("stop_loss_not_above_entry")
    previous = None
    for target_price in target_prices:
        if target_price <= 0:
            reasons.append("take_profit_price_invalid")
            continue
        if side_norm == "long":
            if target_price <= entry_price:
                reasons.append("take_profit_not_above_entry")
            if previous is not None and target_price < previous:
                reasons.append("take_profit_targets_not_monotonic")
        else:
            if target_price >= entry_price:
                reasons.append("take_profit_not_below_entry")
            if previous is not None and target_price > previous:
                reasons.append("take_profit_targets_not_monotonic")
        previous = target_price
    return reasons


def validate_exit_plan(
    *,
    side: str,
    entry_price: Decimal,
    stop_plan: dict[str, Any] | None,
    tp_plan: dict[str, Any] | None,
    leverage: Decimal | None = None,
    allowed_leverage: int | None = None,
    max_position_risk_pct: float | None = None,
    risk_trade_action: str | None = None,
    fee_bps: Decimal | None = None,
    slippage_bps: Decimal | None = None,
    check_liquidation_buffer: bool = True,
    min_liquidation_buffer_bps: Decimal = Decimal("35"),
    mark_price: Decimal | None = None,
    fill_price: Decimal | None = None,
    gap_stop_max_ratio: float = 0.4,
    market_family: str | None = None,
    spread_bps: Decimal | None = None,
    tick_size_bps: Decimal | None = None,
    price_tick_size: Decimal | None = None,
    volatility_bps: Decimal | None = None,
    depth_ratio: float | None = None,
    quantity_step: Decimal | None = None,
    quantity_min: Decimal | None = None,
    quantity_max: Decimal | None = None,
    trading_status: str | None = None,
    session_trade_allowed: bool | None = None,
    session_open_new_positions_allowed: bool | None = None,
    catalog_snapshot_id: str | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    stop_copy = _copy_plan(stop_plan)
    tp_copy = _copy_plan(tp_plan)
    if stop_copy is not None:
        _ensure_execution_defaults(stop_copy)
    if tp_copy is not None:
        _ensure_execution_defaults(tp_copy)

    stop_price = _dec((stop_copy or {}).get("stop_price"))
    stop_ref = stop_price if stop_price > 0 else None
    targets = [_dec(item.get("target_price")) for item in ((tp_copy or {}).get("targets") or [])]
    reasons.extend(_price_relation_valid(side=side, entry_price=entry_price, stop_price=stop_ref, target_prices=targets))
    if session_trade_allowed is False:
        reasons.append("instrument_session_not_tradeable")
    if session_open_new_positions_allowed is False:
        reasons.append("instrument_open_session_restricted")
    if trading_status:
        lowered_status = str(trading_status).strip().lower()
        if lowered_status in {"maintain", "off", "restrictedapi"}:
            reasons.append(f"instrument_status_{lowered_status}")

    total_take_pct = Decimal("0")
    for item in (tp_copy or {}).get("targets") or []:
        pct = _take_pct(item)
        if pct <= 0:
            reasons.append("take_profit_pct_invalid")
            continue
        total_take_pct += pct
    if total_take_pct > Decimal("1.00000001"):
        reasons.append("take_profit_pct_sum_exceeds_1")

    if risk_trade_action == "do_not_trade":
        reasons.append("risk_engine_blocks_exit_plan")

    leverage_value = leverage if leverage is not None else Decimal("0")
    stop_distance_bps = None
    stop_budget_bps = None
    stop_budget_meta = None
    if stop_ref is not None and entry_price > 0:
        stop_distance_bps = abs(entry_price - stop_ref) / entry_price * Decimal("10000")
    if leverage_value > 0 and stop_ref is not None and entry_price > 0:
        stop_budget_bps = leverage_indexed_stop_budget_bps(leverage_value)
        stop_budget_meta = executable_stop_floor_bps(
            market_family=market_family,
            spread_bps=spread_bps,
            tick_size_bps=tick_size_bps,
            volatility_bps=volatility_bps,
            depth_ratio=depth_ratio,
            liquidation_buffer_bps=min_liquidation_buffer_bps if check_liquidation_buffer else None,
        )
        executable_floor_bps = stop_budget_meta["executable_floor_bps"]
        if stop_budget_bps is not None and stop_distance_bps is not None and stop_distance_bps > stop_budget_bps:
            reasons.append("stop_distance_exceeds_leverage_budget")
        if stop_distance_bps is not None and stop_distance_bps < executable_floor_bps:
            reasons.append("stop_distance_below_executable_floor")
        if (
            stop_budget_bps is not None
            and executable_floor_bps > stop_budget_bps
        ):
            reasons.append("leverage_budget_infeasible_for_market_microstructure")

    if (
        check_liquidation_buffer
        and stop_ref is not None
        and leverage_value > 0
        and entry_price > 0
    ):
        liq_px = approximate_isolated_liquidation_price(
            side=side,
            entry_price=entry_price,
            leverage=leverage_value,
        )
        if liq_px is not None and liq_px > 0:
            buf = entry_price * (min_liquidation_buffer_bps / Decimal("10000"))
            sn = str(side).lower()
            if sn == "long" and stop_ref < liq_px + buf:
                reasons.append("stop_inside_liquidation_buffer")
            if sn == "short" and stop_ref > liq_px - buf:
                reasons.append("stop_inside_liquidation_buffer")

    if (
        stop_ref is not None
        and mark_price is not None
        and fill_price is not None
        and entry_price > 0
        and mark_price > 0
    ):
        gap_bps = abs(mark_price - fill_price) / mark_price * Decimal("10000")
        stop_dist = abs(entry_price - stop_ref) / entry_price * Decimal("10000")
        if stop_dist > 0 and gap_bps / stop_dist > Decimal(str(gap_stop_max_ratio)):
            reasons.append("exit_plan_gap_stop_too_tight_vs_spread")
    if allowed_leverage is not None and leverage_value > Decimal(str(allowed_leverage)):
        reasons.append("exit_plan_exceeds_allowed_leverage")

    if price_tick_size is not None and price_tick_size > 0:
        for candidate, code in (
            (stop_ref, "stop_price_not_aligned_to_tick"),
            *[(target, "take_profit_not_aligned_to_tick") for target in targets],
        ):
            if candidate is None or candidate <= 0:
                continue
            remainder = candidate % price_tick_size
            if remainder != 0:
                reasons.append(code)
                break

    initial_qty = _dec(((tp_copy or {}).get("execution_state") or {}).get("initial_qty"))
    if quantity_min is not None and quantity_min > 0 and initial_qty > 0 and initial_qty < quantity_min:
        reasons.append("exit_plan_initial_qty_below_minimum")
    if quantity_max is not None and quantity_max > 0 and initial_qty > quantity_max:
        reasons.append("exit_plan_initial_qty_above_maximum")
    if quantity_step is not None and quantity_step > 0:
        for item in (tp_copy or {}).get("targets") or []:
            pct = _take_pct(item)
            if pct <= 0 or initial_qty <= 0:
                continue
            target_qty = initial_qty * pct
            if quantity_min is not None and quantity_min > 0 and target_qty < quantity_min:
                reasons.append("exit_plan_partial_qty_below_minimum")
                break

    position_risk_pct = None
    if leverage_value > 0 and stop_ref is not None and entry_price > 0:
        fee_pct = (fee_bps or Decimal("0")) / Decimal("10000")
        slippage_pct = (slippage_bps or Decimal("0")) / Decimal("10000")
        stop_distance_pct = abs(entry_price - stop_ref) / entry_price
        position_risk_pct = float((stop_distance_pct + fee_pct + slippage_pct) * leverage_value)
        if max_position_risk_pct is not None and position_risk_pct > max_position_risk_pct:
            reasons.append("exit_plan_position_risk_exceeds_max")

    return {
        "valid": not reasons,
        "reasons": reasons,
        "metrics": {
            "position_risk_pct": position_risk_pct,
            "take_pct_sum": float(total_take_pct) if total_take_pct > 0 else 0.0,
            "stop_distance_bps": float(stop_distance_bps) if stop_distance_bps is not None else None,
            "stop_budget_bps": float(stop_budget_bps) if stop_budget_bps is not None else None,
            "stop_budget_meta": (
                {key: float(value) for key, value in (stop_budget_meta or {}).items()}
                if stop_budget_meta is not None
                else None
            ),
            "trading_status": trading_status,
            "session_trade_allowed": session_trade_allowed,
            "session_open_new_positions_allowed": session_open_new_positions_allowed,
            "catalog_snapshot_id": catalog_snapshot_id,
        },
        "stop_plan": stop_copy,
        "tp_plan": tp_copy,
    }


def _truthy_flag(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes", "on"):
        return True
    return False


def evaluate_exit_plan(
    *,
    side: str,
    entry_price: Decimal,
    current_qty: Decimal,
    mark_price: Decimal,
    fill_price: Decimal,
    stop_plan: dict[str, Any] | None,
    tp_plan: dict[str, Any] | None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    stop_next = _copy_plan(stop_plan)
    tp_next = _copy_plan(tp_plan)
    if stop_next is not None:
        _ensure_execution_defaults(stop_next)
    if tp_next is not None:
        _ensure_execution_defaults(tp_next)

    def _execution_for_close() -> dict[str, Any]:
        if stop_next is not None:
            return dict(stop_next.get("execution") or {})
        if tp_next is not None:
            return dict(tp_next.get("execution") or {})
        return {}

    if current_qty > 0 and stop_next is not None and _truthy_flag(stop_next.get("force_emergency_close")):
        execution = _execution_for_close()
        trigger = pick_trigger_price(str(stop_next.get("trigger_type") or "mark_price"), mark_price, fill_price)
        stop_next["force_emergency_close"] = False
        return {
            "policy_version": EXIT_POLICY_VERSION,
            "actions": [
                {
                    "action": "close_full",
                    "reason_code": "emergency_flatten",
                    "qty": str(current_qty),
                    "reduce_only": bool(execution.get("reduce_only", True)),
                    "order_type": execution.get("order_type") or "market",
                    "timing": execution.get("timing") or "immediate",
                    "cancel_replace_behavior": execution.get("cancel_replace_behavior"),
                    "estimated_fee_bps": execution.get("estimated_fee_bps"),
                    "estimated_slippage_bps": execution.get("estimated_slippage_bps"),
                    "trigger_price": str(trigger),
                }
            ],
            "reasons": ["emergency_flatten"],
            "updated_stop_plan": stop_next,
            "updated_tp_plan": tp_next,
        }

    if current_qty > 0 and now_ms is not None:
        for holder, _ in ((stop_next, "stop_next"), (tp_next, "tp_next")):
            if holder is None:
                continue
            ts = holder.get("time_stop")
            if not isinstance(ts, dict) or not ts.get("enabled") or ts.get("fired"):
                continue
            dl = int(ts.get("deadline_ts_ms") or 0)
            if dl <= 0 or now_ms < dl:
                continue
            ts_u = {**ts, "fired": True}
            holder["time_stop"] = ts_u
            execution = _execution_for_close()
            trigger = pick_trigger_price(
                str((stop_next or tp_next or {}).get("trigger_type") or "mark_price"),
                mark_price,
                fill_price,
            )
            return {
                "policy_version": EXIT_POLICY_VERSION,
                "actions": [
                    {
                        "action": "close_full",
                        "reason_code": "time_stop_expired",
                        "qty": str(current_qty),
                        "reduce_only": bool(execution.get("reduce_only", True)),
                        "order_type": execution.get("order_type") or "market",
                        "timing": execution.get("timing") or "immediate",
                        "cancel_replace_behavior": execution.get("cancel_replace_behavior"),
                        "estimated_fee_bps": execution.get("estimated_fee_bps"),
                        "estimated_slippage_bps": execution.get("estimated_slippage_bps"),
                        "trigger_price": str(trigger),
                    }
                ],
                "reasons": ["time_stop_expired"],
                "updated_stop_plan": stop_next,
                "updated_tp_plan": tp_next,
            }

    exec_state = dict((tp_next or {}).get("execution_state") or {})
    already_hit = {int(item) for item in (exec_state.get("hit_tp_indices") or [])}
    hit_stop, hit_tps = eval_stop_tp_full(
        side=side,
        mark=mark_price,
        fill=fill_price,
        stop_plan=stop_next,
        tp_plan=tp_next,
        already_hit_tp=already_hit,
    )

    actions: list[dict[str, Any]] = []
    reasons: list[str] = []
    tp_default = str((tp_next or {}).get("trigger_type") or "fill_price")

    if hit_stop and stop_next is not None and current_qty > 0:
        execution = stop_next.get("execution") or {}
        actions.append(
            {
                "action": "close_full",
                "reason_code": "stop_loss_hit",
                "qty": str(current_qty),
                "reduce_only": bool(execution.get("reduce_only", True)),
                "order_type": execution.get("order_type") or "market",
                "timing": execution.get("timing") or "immediate",
                "cancel_replace_behavior": execution.get("cancel_replace_behavior"),
                "estimated_fee_bps": execution.get("estimated_fee_bps"),
                "estimated_slippage_bps": execution.get("estimated_slippage_bps"),
                "trigger_price": str(
                    pick_trigger_price(str(stop_next.get("trigger_type") or "mark_price"), mark_price, fill_price)
                ),
                "stop_price": stop_next.get("stop_price"),
            }
        )
        reasons.append("stop_loss_hit")
        return {
            "policy_version": EXIT_POLICY_VERSION,
            "actions": actions,
            "reasons": reasons,
            "updated_stop_plan": stop_next,
            "updated_tp_plan": tp_next,
        }

    if runner_trail_hit(
        side=side,
        mark=mark_price,
        fill=fill_price,
        tp_plan=tp_next,
        trigger_default=tp_default,
    ) and current_qty > 0:
        runner = dict((tp_next or {}).get("runner") or {})
        execution = (tp_next or {}).get("execution") or {}
        actions.append(
            {
                "action": "close_full",
                "reason_code": "runner_trail_hit",
                "qty": str(current_qty),
                "reduce_only": bool(execution.get("reduce_only", True)),
                "order_type": execution.get("order_type") or "market",
                "timing": execution.get("timing") or "immediate",
                "cancel_replace_behavior": execution.get("cancel_replace_behavior"),
                "estimated_fee_bps": execution.get("estimated_fee_bps"),
                "estimated_slippage_bps": execution.get("estimated_slippage_bps"),
                "trigger_price": str(
                    pick_trigger_price(str(runner.get("trigger_type") or tp_default), mark_price, fill_price)
                ),
                "trail_stop": runner.get("trail_stop"),
            }
        )
        reasons.append("runner_trail_hit")
        return {
            "policy_version": EXIT_POLICY_VERSION,
            "actions": actions,
            "reasons": reasons,
            "updated_stop_plan": stop_next,
            "updated_tp_plan": tp_next,
        }

    remaining_qty = current_qty
    initial_qty = _dec(exec_state.get("initial_qty"), default=str(current_qty))
    targets = (tp_next or {}).get("targets") or []
    for index in sorted(hit_tps):
        if index in already_hit or index >= len(targets) or remaining_qty <= 0:
            continue
        target = dict(targets[index])
        qty_close = (initial_qty * _take_pct(target)).quantize(Decimal("0.00000001"))
        qty_close = min(qty_close, remaining_qty)
        if qty_close <= 0:
            continue
        execution = (tp_next or {}).get("execution") or {}
        actions.append(
            {
                "action": "close_partial",
                "reason_code": "take_profit_hit",
                "tp_index": index,
                "qty": str(qty_close),
                "reduce_only": bool(execution.get("reduce_only", True)),
                "order_type": execution.get("order_type") or "market",
                "timing": execution.get("timing") or "immediate",
                "cancel_replace_behavior": execution.get("cancel_replace_behavior"),
                "estimated_fee_bps": execution.get("estimated_fee_bps"),
                "estimated_slippage_bps": execution.get("estimated_slippage_bps"),
                "trigger_price": str(
                    pick_trigger_price(str(target.get("trigger_type") or tp_default), mark_price, fill_price)
                ),
                "target_price": target.get("target_price"),
            }
        )
        reasons.append(f"take_profit_hit_{index}")
        remaining_qty -= qty_close
        already_hit.add(index)
        exec_state["hit_tp_indices"] = sorted(already_hit)
        if tp_next is not None:
            tp_next["execution_state"] = exec_state
        runner = dict((tp_next or {}).get("runner") or {})
        if (
            index == int(runner.get("arm_after_tp_index") or 1)
            and runner.get("enabled")
            and not runner.get("armed")
        ):
            runner["armed"] = True
            runner, changed = update_runner_state(side=side, fill_price=fill_price, runner=runner)
            if changed:
                reasons.append("runner_armed")
            if tp_next is not None:
                tp_next["runner"] = runner

    stop_next, tp_next, break_even_applied = apply_break_even_update(
        side=side,
        entry_price=entry_price,
        stop_plan=stop_next,
        tp_plan=tp_next,
    )
    if break_even_applied:
        actions.append({"action": "plan_update", "reason_code": "break_even_applied"})
        reasons.append("break_even_applied")

    runner_live = dict((tp_next or {}).get("runner") or {})
    if runner_live.get("armed"):
        runner_live, changed = update_runner_state(
            side=side,
            fill_price=fill_price,
            runner=runner_live,
        )
        if changed:
            if tp_next is not None:
                tp_next["runner"] = runner_live
            actions.append(
                {
                    "action": "plan_update",
                    "reason_code": "trailing_updated",
                    "trail_stop": runner_live.get("trail_stop"),
                }
            )
            reasons.append("trailing_updated")

    return {
        "policy_version": EXIT_POLICY_VERSION,
        "actions": actions,
        "reasons": reasons,
        "updated_stop_plan": stop_next,
        "updated_tp_plan": tp_next,
    }


def run_unified_exit_evaluation(**kwargs: Any) -> dict[str, Any]:
    """Gleicher Fachpfad wie evaluate_exit_plan (expliziter API-Name)."""
    return evaluate_exit_plan(**kwargs)
