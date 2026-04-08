from __future__ import annotations

from decimal import Decimal

from paper_broker.risk.trigger_eval import (
    eval_stop_tp_full,
    eval_triggers,
    pick_trigger_price,
    runner_trail_hit,
)


def test_pick_trigger_price() -> None:
    assert pick_trigger_price("mark_price", Decimal("100"), Decimal("99")) == Decimal(
        "100"
    )
    assert pick_trigger_price("fill_price", Decimal("100"), Decimal("99")) == Decimal(
        "99"
    )


def test_eval_triggers_long_stop_tp() -> None:
    r = eval_triggers(
        "long",
        Decimal("99"),
        Decimal("100"),
        [Decimal("101"), Decimal("110")],
    )
    assert r.hit_stop
    assert r.hit_targets == []

    r_hit_tp = eval_triggers(
        "long", Decimal("105"), Decimal("100"), [Decimal("101"), Decimal("110")]
    )
    assert not r_hit_tp.hit_stop
    assert r_hit_tp.hit_targets == [0]

    r2 = eval_triggers("long", Decimal("100.5"), Decimal("100"), [Decimal("101")])
    assert not r2.hit_stop
    assert r2.hit_targets == []


def test_eval_triggers_short() -> None:
    r = eval_triggers(
        "short",
        Decimal("101"),
        Decimal("100"),
        [Decimal("99")],
    )
    assert r.hit_stop
    assert r.hit_targets == []

    r_tp = eval_triggers("short", Decimal("98"), Decimal("100"), [Decimal("99")])
    assert not r_tp.hit_stop
    assert r_tp.hit_targets == [0]


def test_eval_stop_tp_full_per_target_trigger() -> None:
    stop_plan = {"trigger_type": "mark_price", "stop_price": "50"}
    tp_plan = {
        "trigger_type": "fill_price",
        "targets": [
            {"target_price": "120", "trigger_type": "mark_price"},
            {"target_price": "130"},
        ],
    }
    hit_s, hit_t = eval_stop_tp_full(
        side="long",
        mark=Decimal("125"),
        fill=Decimal("100"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        already_hit_tp=set(),
    )
    assert not hit_s
    assert hit_t == [0]

    hit_s2, hit_t2 = eval_stop_tp_full(
        side="long",
        mark=Decimal("125"),
        fill=Decimal("135"),
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        already_hit_tp={0},
    )
    assert not hit_s2
    assert hit_t2 == [1]


def test_runner_trail_hit() -> None:
    tp_plan = {
        "runner": {"armed": True, "trail_stop": "98"},
        "trigger_type": "fill_price",
    }
    assert runner_trail_hit(
        side="long",
        mark=Decimal("100"),
        fill=Decimal("97"),
        tp_plan=tp_plan,
        trigger_default="fill_price",
    )
    assert not runner_trail_hit(
        side="long",
        mark=Decimal("100"),
        fill=Decimal("99"),
        tp_plan=tp_plan,
        trigger_default="fill_price",
    )
