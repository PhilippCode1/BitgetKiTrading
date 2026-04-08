from __future__ import annotations

from decimal import Decimal

import pytest
from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.tp_planner import build_tp_plan


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


def test_build_tp_plan_three_atr_targets(settings: PaperBrokerSettings) -> None:
    conn = _EmptyConn()
    atr = Decimal("1000")
    plan = build_tp_plan(
        conn,
        symbol="BTCUSDT",
        timeframe="5m",
        side="long",
        entry=Decimal("60000"),
        atr=atr,
        settings=settings,
        tp_trigger_default="fill_price",
        initial_qty=Decimal("1"),
    )
    assert plan["timeframe"] == "5m"
    assert len(plan["targets"]) == 3
    prices = [Decimal(str(t["target_price"])) for t in plan["targets"]]
    assert prices == sorted(prices)
    assert all(p > Decimal("60000") for p in prices)
    assert plan["runner"]["enabled"] is True
    assert plan["runner"]["trail_offset"] == "1000.0"
    assert plan["break_even"]["trigger_after_tp_index"] == 0
    assert plan["execution_state"]["initial_qty"] == "1"
    assert plan["execution_state"]["hit_tp_indices"] == []
