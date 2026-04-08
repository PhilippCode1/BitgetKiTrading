from __future__ import annotations

from learning_engine.training.example_ranges import label_ranges_for_examples


def test_label_ranges_use_decision_to_closed() -> None:
    examples = [
        {"decision_ts_ms": 100, "closed_ts_ms": 200},
        {"decision_ts_ms": 150, "closed_ts_ms": None},
    ]
    r = label_ranges_for_examples(examples)
    assert r[0].start == 100 and r[0].end == 200
    assert r[1].start == 150 and r[1].end == 150
