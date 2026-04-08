from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from paper_broker.config import PaperBrokerSettings
from paper_broker.strategy.engine import StrategyExecutionEngine
from paper_broker.strategy.registry import pick_strategy


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> PaperBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("STRATEGY_EXEC_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "auto")
    return PaperBrokerSettings()


def test_engine_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("STRATEGY_EXEC_ENABLED", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    s = PaperBrokerSettings()
    broker = MagicMock()
    eng = StrategyExecutionEngine(s, broker)
    eng.handle_signal_created({"signal_id": str(uuid4())}, "BTCUSDT")
    broker.open_position.assert_not_called()


def test_engine_skips_when_global_execution_mode_is_not_paper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("STRATEGY_EXEC_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "auto")
    s = PaperBrokerSettings()
    broker = MagicMock()
    eng = StrategyExecutionEngine(s, broker)
    eng.handle_signal_created({"signal_id": str(uuid4())}, "BTCUSDT")
    broker.open_position.assert_not_called()


def test_pick_strategy_and_intent_kern(settings: PaperBrokerSettings) -> None:
    sig = {
        "signal_class": "kern",
        "direction": "long",
    }
    strat = pick_strategy(settings, sig)
    assert strat.name == "TrendContinuationStrategy"
    intent = strat.build_order_intent(sig, {})
    assert intent.side == "long"
    assert intent.qty_base == Decimal(str(settings.strat_base_qty_btc))


def test_pick_strategy_mikro_mult(settings: PaperBrokerSettings) -> None:
    sig = {"signal_class": "mikro", "direction": "short"}
    strat = pick_strategy(settings, sig)
    intent = strat.build_order_intent(sig, {})
    exp = Decimal(str(settings.strat_base_qty_btc)) * Decimal(
        str(settings.micro_size_mult)
    )
    assert intent.qty_base == exp


def test_strategy_caps_higher_default_leverage_without_clean_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("PAPER_DEFAULT_LEVERAGE", "15")
    s = PaperBrokerSettings()
    strat = pick_strategy(s, {"signal_class": "kern", "direction": "long"})
    intent = strat.build_order_intent({"signal_class": "kern", "direction": "long"}, {})
    assert intent.leverage == Decimal("7")


def test_strategy_keeps_higher_default_leverage_for_clean_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("PAPER_DEFAULT_LEVERAGE", "15")
    s = PaperBrokerSettings()
    sig = {
        "signal_class": "gross",
        "direction": "long",
        "expected_return_bps": 22.0,
        "expected_mae_bps": 18.0,
        "expected_mfe_bps": 30.0,
    }
    strat = pick_strategy(s, sig)
    intent = strat.build_order_intent(sig, {})
    assert intent.leverage == Decimal("15")


def test_strategy_prefers_signal_recommended_leverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("PAPER_DEFAULT_LEVERAGE", "15")
    s = PaperBrokerSettings()
    sig = {
        "signal_class": "gross",
        "direction": "long",
        "recommended_leverage": 11,
        "allowed_leverage": 14,
    }
    strat = pick_strategy(s, sig)
    intent = strat.build_order_intent(sig, {})
    assert intent.leverage == Decimal("11")
