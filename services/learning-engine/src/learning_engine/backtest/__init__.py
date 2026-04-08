from __future__ import annotations

from learning_engine.backtest.splits import (
    Range,
    purged_kfold_embargo,
    purged_kfold_embargo_indices,
    walk_forward_indices,
    walk_forward_splits,
)

__all__ = [
    "build_backtests_router",
    "Range",
    "purged_kfold_embargo",
    "purged_kfold_embargo_indices",
    "walk_forward_indices",
    "walk_forward_splits",
]


def __getattr__(name: str):
    if name == "build_backtests_router":
        from learning_engine.backtest.routes import build_backtests_router

        return build_backtests_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
