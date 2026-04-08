from __future__ import annotations

from unittest.mock import MagicMock

from paper_broker.strategy.registry import is_strategy_registry_allowlisted


def test_registry_filter_off_always_allows() -> None:
    s = MagicMock()
    s.strategy_registry_enabled = False
    assert is_strategy_registry_allowlisted(s, {"X"}, "Y") is True


def test_registry_empty_snapshot_allow_all() -> None:
    s = MagicMock()
    s.strategy_registry_enabled = True
    assert is_strategy_registry_allowlisted(s, set(), "BreakoutBoxStrategy") is True


def test_registry_snapshot_enforces_name() -> None:
    s = MagicMock()
    s.strategy_registry_enabled = True
    assert (
        is_strategy_registry_allowlisted(
            s, {"BreakoutBoxStrategy"}, "TrendContinuationStrategy"
        )
        is False
    )
    assert (
        is_strategy_registry_allowlisted(
            s, {"BreakoutBoxStrategy"}, "BreakoutBoxStrategy"
        )
        is True
    )
