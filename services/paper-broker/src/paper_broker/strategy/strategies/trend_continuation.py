from __future__ import annotations

from typing import Any

from paper_broker.config import PaperBrokerSettings
from paper_broker.strategy.sizing import (
    leverage_for_signal,
    qty_with_stop_budget,
)
from paper_broker.strategy.strategies.base import OrderIntent


class TrendContinuationStrategy:
    name = "TrendContinuationStrategy"

    def __init__(self, settings: PaperBrokerSettings) -> None:
        self._settings = settings

    def should_enter(self, signal: dict[str, Any], context: dict[str, Any]) -> bool:
        del context
        if str(signal.get("signal_class", "")).lower() != "kern":
            return False
        d = str(signal.get("direction", "neutral")).lower()
        return d in ("long", "short")

    def build_order_intent(self, signal: dict[str, Any], context: dict[str, Any]) -> OrderIntent:
        side = str(signal["direction"]).lower()
        qty = qty_with_stop_budget(
            self._settings, signal, "kern", context=context
        )
        lev = leverage_for_signal(self._settings, signal)
        return OrderIntent(side=side, qty_base=qty, leverage=lev, entry_type="market")
