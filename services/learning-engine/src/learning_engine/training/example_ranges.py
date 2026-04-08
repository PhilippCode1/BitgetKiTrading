from __future__ import annotations

from typing import Any

from learning_engine.backtest.splits import Range


def label_ranges_for_examples(examples: list[dict[str, Any]]) -> list[Range]:
    """Label-Zeitintervall: decision_ts_ms .. closed_ts_ms (Trade-Dauer fuer Purging)."""
    out: list[Range] = []
    for ex in examples:
        start = int(ex.get("decision_ts_ms") or 0)
        closed = ex.get("closed_ts_ms")
        end = int(closed) if closed is not None else start
        if end < start:
            end = start
        out.append(Range(start=start, end=end))
    return out
