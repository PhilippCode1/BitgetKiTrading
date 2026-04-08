from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from shared_py.exit_engine import (
    eval_stop_tp_full as shared_eval_stop_tp_full,
    pick_trigger_price as shared_pick_trigger_price,
    runner_trail_hit as shared_runner_trail_hit,
)


@dataclass(frozen=True)
class TriggerResult:
    hit_stop: bool
    hit_targets: list[int]


def pick_trigger_price(trigger_type: str, mark: Decimal, fill: Decimal) -> Decimal:
    return shared_pick_trigger_price(trigger_type, mark, fill)


def eval_triggers(
    side: str,
    trigger_price: Decimal,
    stop_price: Decimal | None,
    targets: list[Decimal],
) -> TriggerResult:
    hit_stop = False
    if stop_price is not None:
        if side == "long" and trigger_price <= stop_price:
            hit_stop = True
        if side == "short" and trigger_price >= stop_price:
            hit_stop = True

    hit_targets: list[int] = []
    for i, tp in enumerate(targets):
        if side == "long" and trigger_price >= tp:
            hit_targets.append(i)
        if side == "short" and trigger_price <= tp:
            hit_targets.append(i)

    return TriggerResult(hit_stop=hit_stop, hit_targets=hit_targets)


def eval_stop_tp_full(
    *,
    side: str,
    mark: Decimal,
    fill: Decimal,
    stop_plan: dict[str, Any] | None,
    tp_plan: dict[str, Any] | None,
    already_hit_tp: set[int],
) -> tuple[bool, list[int]]:
    return shared_eval_stop_tp_full(
        side=side,
        mark=mark,
        fill=fill,
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        already_hit_tp=already_hit_tp,
    )


def runner_trail_hit(
    *,
    side: str,
    mark: Decimal,
    fill: Decimal,
    tp_plan: dict[str, Any] | None,
    trigger_default: str,
) -> bool:
    return shared_runner_trail_hit(
        side=side,
        mark=mark,
        fill=fill,
        tp_plan=tp_plan,
        trigger_default=trigger_default,
    )
