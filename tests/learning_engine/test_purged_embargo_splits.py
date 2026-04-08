from __future__ import annotations

from learning_engine.backtest.splits import (
    Range,
    purged_kfold_embargo_indices,
    walk_forward_indices,
)


def _ranges(n: int) -> list[Range]:
    return [Range(i * 10, i * 10 + 5) for i in range(n)]


def test_purged_kfold_deterministic_length() -> None:
    r = _ranges(20)
    splits = purged_kfold_embargo_indices(r, k=5, embargo_pct=0.05)
    assert len(splits) == 5
    for train_idx, test_idx in splits:
        assert len(test_idx) == 4
        assert len(set(train_idx) & set(test_idx)) == 0


def test_walk_forward_train_only_past_indices() -> None:
    r = _ranges(15)
    splits = walk_forward_indices(r, k=3, embargo_pct=0.0)
    assert len(splits) == 3
    for fi, (train_idx, test_idx) in enumerate(splits):
        lo = fi * 5
        hi = (fi + 1) * 5
        assert test_idx == list(range(lo, hi))
        assert all(j < lo for j in train_idx)


def test_embargo_excludes_indices_after_test_block() -> None:
    r = _ranges(30)
    splits = purged_kfold_embargo_indices(r, k=5, embargo_pct=0.1)
    embargo_n = int(round(30 * 0.1))
    lo0 = 0
    hi0 = 6
    train0, test0 = splits[0]
    assert test0 == list(range(lo0, hi0))
    forbidden = set(range(hi0, min(hi0 + embargo_n, 30)))
    assert forbidden.isdisjoint(set(train0))


def test_walk_forward_purges_overlapping_label_intervals() -> None:
    ranges = [
        Range(0, 100),
        Range(90, 140),
        Range(150, 210),
        Range(220, 280),
    ]
    splits = walk_forward_indices(ranges, k=4, embargo_pct=0.0)
    train_idx, test_idx = splits[1]
    assert test_idx == [1]
    assert train_idx == []
