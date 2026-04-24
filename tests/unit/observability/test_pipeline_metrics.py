from __future__ import annotations

import sys
from pathlib import Path

import pytest
from prometheus_client import REGISTRY, generate_latest

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "shared" / "python" / "src"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from shared_py.observability.metrics import (  # noqa: E402
    inc_pipeline_event_drop,
    set_pipeline_backpressure_queue_size,
)


def _metric_sample_lines(substr: str) -> list[str]:
    return [
        line.decode("utf-8", errors="replace")
        for line in generate_latest(REGISTRY).splitlines()
        if substr in line.decode("utf-8", errors="replace")
    ]


def test_pipeline_backpressure_gauge_exported() -> None:
    set_pipeline_backpressure_queue_size(stream="stream:test_q", size=7)
    lines = _metric_sample_lines("pipeline_backpressure_queue_size")
    assert any('stream="stream:test_q" 7.0' in el.replace("  ", " ") for el in lines) or any(
        "7.0" in el and "stream:test_q" in el for el in lines
    )


def test_pipeline_event_drop_counter_exported() -> None:
    inc_pipeline_event_drop(component="test_comp", reason="test_reason")
    text = generate_latest(REGISTRY).decode("utf-8", errors="replace")
    assert "pipeline_event_drop_total" in text
    assert "test_comp" in text and "test_reason" in text
