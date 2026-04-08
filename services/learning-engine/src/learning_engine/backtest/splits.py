from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Range:
    """Zeitintervall für ein Label (z. B. Trade von open bis close)."""

    start: int
    end: int


def _overlaps(a: Range, b: Range) -> bool:
    return not (a.end <= b.start or a.start >= b.end)


def purged_kfold_embargo_indices(
    ranges: list[Range],
    k: int,
    embargo_pct: float,
) -> list[tuple[list[int], list[int]]]:
    """Wie purged_kfold_embargo, gibt aber Listen von Sample-Indizes zurück."""
    if not ranges or k < 1:
        return []
    n = len(ranges)
    fold_size = max(1, n // k)
    embargo_n = max(0, int(round(n * max(0.0, min(1.0, embargo_pct)))))
    splits: list[tuple[list[int], list[int]]] = []
    for i in range(k):
        lo = i * fold_size
        hi = min((i + 1) * fold_size, n)
        if lo >= n:
            break
        test_idx = list(range(lo, hi))
        if not test_idx:
            continue
        test_block = Range(
            min(ranges[j].start for j in test_idx),
            max(ranges[j].end for j in test_idx),
        )
        embargo_lo = hi
        embargo_hi = min(hi + embargo_n, n)
        embargo_idx = set(range(embargo_lo, embargo_hi))
        train_idx: list[int] = []
        for j in range(n):
            if lo <= j < hi:
                continue
            if j in embargo_idx:
                continue
            if _overlaps(ranges[j], test_block):
                continue
            train_idx.append(j)
        splits.append((train_idx, test_idx))
    return splits


def walk_forward_indices(
    ranges: list[Range],
    k: int,
    embargo_pct: float,
) -> list[tuple[list[int], list[int]]]:
    if not ranges or k < 1:
        return []
    n = len(ranges)
    fold_size = max(1, n // k)
    total_span = max(1, ranges[-1].end - ranges[0].start)
    embargo_ms = int(round(total_span * max(0.0, min(1.0, embargo_pct))))
    splits: list[tuple[list[int], list[int]]] = []
    for i in range(k):
        lo = i * fold_size
        hi = min((i + 1) * fold_size, n)
        if lo >= n:
            break
        test_idx = list(range(lo, hi))
        if not test_idx:
            continue
        test_start = min(ranges[j].start for j in test_idx)
        test_end = max(ranges[j].end for j in test_idx)
        test_block = Range(test_start, test_end)
        train_idx: list[int] = []
        for j in range(n):
            if j >= lo:
                break
            if _overlaps(ranges[j], test_block):
                continue
            if embargo_ms > 0 and test_start - embargo_ms < ranges[j].end <= test_start:
                continue
            train_idx.append(j)
        splits.append((train_idx, test_idx))
    return splits


def purged_kfold_embargo(
    ranges: list[Range],
    k: int,
    embargo_pct: float,
) -> list[tuple[list[Range], list[Range]]]:
    """Kompatibilität: Range-Listen pro Fold."""
    out: list[tuple[list[Range], list[Range]]] = []
    for ti, si in purged_kfold_embargo_indices(ranges, k, embargo_pct):
        out.append(([ranges[j] for j in ti], [ranges[j] for j in si]))
    return out


def walk_forward_splits(
    ranges: list[Range],
    k: int,
    embargo_pct: float,
) -> list[tuple[list[Range], list[Range]]]:
    out: list[tuple[list[Range], list[Range]]] = []
    for ti, si in walk_forward_indices(ranges, k, embargo_pct):
        out.append(([ranges[j] for j in ti], [ranges[j] for j in si]))
    return out


def range_bounds_for_indices(ranges: list[Range], indices: list[int]) -> dict[str, int]:
    if not indices:
        return {"start": 0, "end": 0}
    rs = [ranges[i] for i in indices]
    return {"start": min(r.start for r in rs), "end": max(r.end for r in rs)}
