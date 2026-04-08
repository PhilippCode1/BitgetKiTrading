"""Unit tests: chart_annotation_sanitize (strategy_signal_explain)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_orchestrator.chart_annotation_sanitize import sanitize_strategy_chart_annotations

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "chart_annotations"


def test_sanitize_none() -> None:
    assert sanitize_strategy_chart_annotations(None) == (None, 0)


def test_sanitize_rejects_non_object() -> None:
    assert sanitize_strategy_chart_annotations([]) == (None, 0)
    assert sanitize_strategy_chart_annotations("x") == (None, 0)


def test_sanitize_rejects_wrong_schema_version() -> None:
    assert sanitize_strategy_chart_annotations({"schema_version": "9.9"}) == (None, 0)


def test_converts_ms_time_markers() -> None:
    raw = {
        "schema_version": "1.0",
        "time_markers": [{"time_unix_s": 1_700_000_000_000, "label": "L"}],
    }
    fixed, n = sanitize_strategy_chart_annotations(raw)
    assert n == 1
    assert fixed is not None
    assert fixed["time_markers"][0]["time_unix_s"] == 1_700_000_000


def test_caps_array_lengths() -> None:
    raw = {
        "schema_version": "1.0",
        "horizontal_lines": [{"price": float(i)} for i in range(20)],
    }
    fixed, _ = sanitize_strategy_chart_annotations(raw)
    assert fixed is not None
    assert len(fixed["horizontal_lines"]) == 12


def test_fixture_ms_payload_roundtrip() -> None:
    path = FIXTURES / "strategy_signal_chart_annotations_ms.json"
    assert path.is_file(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    fixed, n = sanitize_strategy_chart_annotations(data["chart_annotations"])
    assert fixed is not None
    assert n >= 1
    m0 = fixed["time_markers"][0]
    assert m0["time_unix_s"] < 10**11
