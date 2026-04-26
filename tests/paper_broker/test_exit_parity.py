from __future__ import annotations

from decimal import Decimal

import pytest

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.tp_planner import build_tp_plan
from shared_py.exit_engine import build_live_exit_plans, evaluate_exit_plan


class _EmptyConn:
    def execute(self, *args: object, **kwargs: object) -> _EmptyConn:
        return self

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list:
        return []


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> PaperBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    return PaperBrokerSettings()


def test_paper_and_live_exit_builders_share_tp_runner_semantics(
    settings: PaperBrokerSettings,
) -> None:
    conn = _EmptyConn()
    paper_tp = build_tp_plan(
        conn,
        symbol="BTCUSDT",
        timeframe="5m",
        side="long",
        entry=Decimal("100"),
        atr=Decimal("3"),
        settings=settings,
        tp_trigger_default="fill_price",
        initial_qty=Decimal("1"),
    )
    _live_stop, live_tp = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("97"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(
            Decimal(str(settings.tp1_pct)),
            Decimal(str(settings.tp2_pct)),
            Decimal(str(settings.tp3_pct)),
        ),
        runner_enabled=settings.exit_runner_enabled,
        runner_trail_mult=Decimal(str(settings.runner_trail_atr_mult)),
        break_even_after_tp_index=settings.exit_break_even_after_tp_index,
        timeframe="5m",
    )

    assert live_tp is not None
    paper_prices = [
        Decimal(str(target["target_price"])) for target in paper_tp["targets"]
    ]
    live_prices = [
        Decimal(str(target["target_price"])) for target in live_tp["targets"]
    ]
    assert live_prices == paper_prices
    assert [target["take_pct"] for target in live_tp["targets"]] == [
        target["take_pct"] for target in paper_tp["targets"]
    ]
    assert live_tp["runner"]["trail_offset"] == paper_tp["runner"]["trail_offset"]
    assert (
        live_tp["runner"]["arm_after_tp_index"]
        == paper_tp["runner"]["arm_after_tp_index"]
    )
    assert (
        live_tp["break_even"]["trigger_after_tp_index"]
        == paper_tp["break_even"]["trigger_after_tp_index"]
    )


def test_paper_and_live_exit_progression_stay_in_parity(
    settings: PaperBrokerSettings,
) -> None:
    conn = _EmptyConn()
    paper_tp = build_tp_plan(
        conn,
        symbol="BTCUSDT",
        timeframe="5m",
        side="long",
        entry=Decimal("100"),
        atr=Decimal("3"),
        settings=settings,
        tp_trigger_default="fill_price",
        initial_qty=Decimal("1"),
    )
    stop_plan, live_tp = build_live_exit_plans(
        side="long",
        entry_price=Decimal("100"),
        initial_qty=Decimal("1"),
        stop_loss=Decimal("97"),
        take_profit=Decimal("109"),
        stop_trigger_type="mark_price",
        tp_trigger_type="fill_price",
        take_pcts=(
            Decimal(str(settings.tp1_pct)),
            Decimal(str(settings.tp2_pct)),
            Decimal(str(settings.tp3_pct)),
        ),
        runner_enabled=settings.exit_runner_enabled,
        runner_trail_mult=Decimal(str(settings.runner_trail_atr_mult)),
        break_even_after_tp_index=settings.exit_break_even_after_tp_index,
        timeframe="5m",
    )

    paper_decision = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("105"),
        fill_price=Decimal("105"),
        stop_plan=stop_plan,
        tp_plan=paper_tp,
    )
    live_decision = evaluate_exit_plan(
        side="long",
        entry_price=Decimal("100"),
        current_qty=Decimal("1"),
        mark_price=Decimal("105"),
        fill_price=Decimal("105"),
        stop_plan=stop_plan,
        tp_plan=live_tp,
    )

    assert live_decision["reasons"] == paper_decision["reasons"]
    assert live_decision["updated_stop_plan"] == paper_decision["updated_stop_plan"]
    assert (
        live_decision["updated_tp_plan"]["execution_state"]
        == paper_decision["updated_tp_plan"]["execution_state"]
    )
    assert (
        live_decision["updated_tp_plan"]["break_even"]
        == paper_decision["updated_tp_plan"]["break_even"]
    )
    assert (
        live_decision["updated_tp_plan"]["runner"]
        == paper_decision["updated_tp_plan"]["runner"]
    )
    assert len(live_decision["actions"]) == len(paper_decision["actions"])
    for live_action, paper_action in zip(
        live_decision["actions"], paper_decision["actions"], strict=True
    ):
        assert live_action["action"] == paper_action["action"]
        assert live_action["reason_code"] == paper_action["reason_code"]
        if "tp_index" in live_action:
            assert live_action["tp_index"] == paper_action["tp_index"]
        if "qty" in live_action:
            assert live_action["qty"] == paper_action["qty"]
        if "target_price" in live_action:
            assert Decimal(str(live_action["target_price"])) == Decimal(
                str(paper_action["target_price"])
            )
