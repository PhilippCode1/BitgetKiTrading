from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class OrderIntent:
    side: str
    qty_base: Decimal
    leverage: Decimal
    entry_type: str


class StrategyV1(Protocol):
    name: str

    def should_enter(self, signal: dict[str, Any], context: dict[str, Any]) -> bool: ...

    def build_order_intent(self, signal: dict[str, Any], context: dict[str, Any]) -> OrderIntent: ...
