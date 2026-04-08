from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_ENGINE_SRC = ROOT / "services" / "learning-engine" / "src"

for candidate in (ROOT, LEARNING_ENGINE_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.registry.models import StrategyScope


def test_strategy_scope_expands_to_canonical_instrument_context() -> None:
    scope = StrategyScope(
        symbol="ethusdt",
        market_family="margin",
        margin_account_mode="crossed",
        metadata_source="registry_test",
        analytics_eligible=True,
        supports_shorting=True,
        supports_leverage=True,
        timeframes=["5m", "1H"],
    )

    assert scope.symbol == "ETHUSDT"
    assert scope.category_key == "bitget:margin:crossed"
    assert scope.canonical_instrument_id == "bitget:margin:crossed:ETHUSDT"
    assert scope.analytics_eligible is True
    assert scope.supports_shorting is True
    assert scope.supports_long_short is True

    instrument = scope.instrument_identity()
    assert instrument.category_key == scope.category_key
    assert instrument.canonical_instrument_id == scope.canonical_instrument_id
    assert instrument.supports_shorting is True
    assert instrument.market_family == "margin"
