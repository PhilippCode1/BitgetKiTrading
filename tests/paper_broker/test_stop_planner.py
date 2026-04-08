from __future__ import annotations

from decimal import Decimal

import pytest
from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.stop_planner import build_stop_plan


class _EmptyConn:
    """DB ohne Zeilen: ATR-Fallback über default_bps."""

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


def test_build_stop_plan_fallback_atr_long(settings: PaperBrokerSettings) -> None:
    conn = _EmptyConn()
    plan, atr = build_stop_plan(
        conn,
        symbol="BTCUSDT",
        timeframe="5m",
        side="long",
        entry=Decimal("60000"),
        settings=settings,
        trigger_type="mark_price",
        method_mix={"volatility": True, "invalidation": False, "liquidity": False},
    )
    assert plan["trigger_type"] == "mark_price"
    assert "stop_price" in plan
    sp = Decimal(str(plan["stop_price"]))
    assert sp < Decimal("60000")
    assert atr > 0
    assert plan["method_mix"]["volatility"] is True
    vb = plan["volatility_basis"]
    assert vb.get("source") == "default_bps" or vb.get("atr_value")


def test_build_stop_plan_short(settings: PaperBrokerSettings) -> None:
    conn = _EmptyConn()
    plan, _atr = build_stop_plan(
        conn,
        symbol="BTCUSDT",
        timeframe="5m",
        side="short",
        entry=Decimal("60000"),
        settings=settings,
        trigger_type="fill_price",
        method_mix={"volatility": True, "invalidation": False, "liquidity": False},
    )
    sp = Decimal(str(plan["stop_price"]))
    assert sp > Decimal("60000")
