from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.market_data import fetch_target_zone_drawings, zone_mid_price
from shared_py.exit_engine import EXIT_POLICY_VERSION, merge_exit_build_overrides


def _atr_targets(
    entry: Decimal, side: str, atr: Decimal, tp_trigger: str
) -> list[dict[str, Any]]:
    s = side.lower()
    sign = Decimal("1") if s == "long" else Decimal("-1")
    mults = [Decimal("0.8"), Decimal("1.6"), Decimal("3.0")]
    out = []
    for i, m in enumerate(mults):
        px = entry + sign * atr * m
        out.append(
            {
                "index": i,
                "target_price": str(px),
                "take_pct": None,
                "order_type": "market",
                "trigger_type": tp_trigger,
                "runner": i == 2,
            }
        )
    return out


def build_tp_plan(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    side: str,
    entry: Decimal,
    atr: Decimal,
    settings: PaperBrokerSettings,
    tp_trigger_default: str,
    initial_qty: Decimal,
    exit_execution_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ov = merge_exit_build_overrides(
        take_pcts=(
            Decimal(str(settings.tp1_pct)),
            Decimal(str(settings.tp2_pct)),
            Decimal(str(settings.tp3_pct)),
        ),
        runner_enabled=bool(settings.exit_runner_enabled),
        runner_trail_mult=Decimal(str(settings.runner_trail_atr_mult)),
        break_even_after_tp_index=int(settings.exit_break_even_after_tp_index),
        hints=exit_execution_hints,
    )
    p1, p2, p3 = ov["take_pcts"]
    trail_offset = atr * ov["runner_trail_mult"]
    arm_idx = int(ov["runner_arm_after_tp_index"])
    if arm_idx < 0 or arm_idx > 2:
        arm_idx = 1
    zones = fetch_target_zone_drawings(conn, symbol, timeframe)
    mids: list[tuple[Decimal, dict[str, Any]]] = []
    for z in zones:
        mid = zone_mid_price(z["geometry"])
        if mid is None:
            continue
        mids.append((mid, z))

    s = side.lower()
    if s == "long":
        mids = [(m, z) for m, z in mids if m > entry]
        mids.sort(key=lambda x: x[0])
    else:
        mids = [(m, z) for m, z in mids if m < entry]
        mids.sort(key=lambda x: x[0], reverse=True)

    targets: list[dict[str, Any]] = []
    if len(mids) >= 3:
        for i in range(3):
            m, z = mids[i]
            pct = p1 if i == 0 else p2 if i == 1 else p3
            targets.append(
                {
                    "index": i,
                    "target_price": str(m),
                    "take_pct": str(pct),
                    "order_type": "market",
                    "trigger_type": tp_trigger_default,
                    "runner": i == 2,
                    "drawing_id": z.get("drawing_id"),
                }
            )
    else:
        raw = _atr_targets(entry, side, atr, tp_trigger_default)
        for i, t in enumerate(raw):
            t["take_pct"] = str(p1 if i == 0 else p2 if i == 1 else p3)
            targets.append(t)

    return {
        "policy_version": EXIT_POLICY_VERSION,
        "timeframe": timeframe,
        "trigger_type": tp_trigger_default,
        "targets": targets,
        "execution": {
            "reduce_only": True,
            "order_type": "market",
            "timing": "immediate",
            "estimated_fee_bps": "0",
            "estimated_slippage_bps": "0",
            "cancel_replace_behavior": "cancel_existing_reduce_only_then_submit",
        },
        "runner": {
            "enabled": bool(ov["runner_enabled"]),
            "mode": "fixed_offset",
            "trail_atr_mult": str(ov["runner_trail_mult"]),
            "trail_offset": str(trail_offset),
            "arm_after_tp2": arm_idx >= 2,
            "arm_after_tp_index": arm_idx,
            "armed": False,
            "high_water": None,
            "low_water": None,
            "trail_stop": None,
            "activation_price": None,
            "wick_confirm_consecutive_ticks": 2,
            "wick_breach_streak": 0,
        },
        "break_even": {
            "enabled": True,
            "trigger_after_tp_index": int(ov["break_even_after_tp_index"]),
            "applied": False,
        },
        "execution_state": {
            "hit_tp_indices": [],
            "initial_qty": str(initial_qty),
        },
    }
