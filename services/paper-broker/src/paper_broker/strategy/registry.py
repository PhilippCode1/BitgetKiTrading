from __future__ import annotations

from typing import Any

from paper_broker.config import PaperBrokerSettings
from paper_broker.strategy.strategies.breakout_box import BreakoutBoxStrategy
from paper_broker.strategy.strategies.mean_reversion_micro import MeanReversionMicroStrategy
from paper_broker.strategy.strategies.trend_continuation import TrendContinuationStrategy
from paper_broker.strategy.strategies.base import StrategyV1


def is_strategy_registry_allowlisted(
    settings: PaperBrokerSettings,
    promoted_names: set[str],
    strategy_name: str,
) -> bool:
    """Wenn Registry aktiv und Snapshot nicht leer: nur gelistete Namen."""
    if not settings.strategy_registry_enabled:
        return True
    if not promoted_names:
        return True
    return strategy_name in promoted_names


def pick_strategy(settings: PaperBrokerSettings, signal: dict[str, Any]) -> StrategyV1:
    cls = str(signal.get("signal_class", "kern")).lower()
    if cls == "mikro":
        return MeanReversionMicroStrategy(settings)
    if cls == "gross":
        return BreakoutBoxStrategy(settings)
    return TrendContinuationStrategy(settings)
