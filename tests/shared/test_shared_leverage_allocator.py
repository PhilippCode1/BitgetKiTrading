from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
shared_src_str = str(SHARED_SRC)
if SHARED_SRC.is_dir() and shared_src_str not in sys.path:
    sys.path.insert(0, shared_src_str)

from shared_py.leverage_allocator import (
    allocate_integer_leverage,
    normalize_leverage_cap,
)


def test_allocate_integer_leverage_uses_lowest_cap() -> None:
    decision = allocate_integer_leverage(
        requested_leverage=25,
        caps={
            "exchange_cap": 30,
            "model_cap": 18,
            "drawdown_cap": 12,
        },
    )
    assert decision["allowed_leverage"] == 12
    assert decision["recommended_leverage"] == 12
    assert decision["binding_cap_names"] == ["drawdown_cap"]
    assert "drawdown_cap_binding" in decision["cap_reasons_json"]


def test_normalize_leverage_cap_floors_float_and_clamps_max() -> None:
    assert normalize_leverage_cap(7.9) == 7
    assert normalize_leverage_cap(80, max_leverage=75) == 75
    assert normalize_leverage_cap(None) is None
    assert normalize_leverage_cap("") is None
    assert normalize_leverage_cap("12.3") == 12
    assert normalize_leverage_cap("nope") is None
    assert normalize_leverage_cap(object()) is None  # type: ignore[arg-type]


def test_allocate_skips_invalid_caps_and_ties_binding() -> None:
    decision = allocate_integer_leverage(
        requested_leverage=15,
        caps={
            "bad": "x",
            "c1": 15,
            "c2": 15,
        },
    )
    assert decision["allowed_leverage"] == 15
    assert set(decision["binding_cap_names"]) == {"c1", "c2"}


def test_allocate_requested_invalid_uses_max() -> None:
    decision = allocate_integer_leverage(
        requested_leverage="bad",
        caps={"exchange_cap": 40},
    )
    assert decision["requested_leverage"] == 75
    assert decision["allowed_leverage"] == 40


def test_allocate_integer_leverage_blocks_below_minimum() -> None:
    decision = allocate_integer_leverage(
        requested_leverage=20,
        caps={
            "model_cap": 6,
            "exchange_cap": 75,
        },
        blocked_reason="paper_allowed_leverage_below_minimum",
    )
    assert decision["allowed_leverage"] == 6
    assert decision["recommended_leverage"] is None
    assert decision["blocked_reason"] == "paper_allowed_leverage_below_minimum"
    assert "paper_allowed_leverage_below_minimum" in decision["cap_reasons_json"]


def test_allocate_empty_caps_uses_requested_clamped() -> None:
    decision = allocate_integer_leverage(requested_leverage=22, caps={})
    assert decision["allowed_leverage"] == 22
    assert decision["recommended_leverage"] == 22
    assert decision["binding_cap_names"] == []


def test_allocate_negative_cap_normalizes_to_zero_then_blocks_recommendation() -> None:
    decision = allocate_integer_leverage(
        requested_leverage=30,
        caps={"broken_cap": -5},
    )
    assert decision["allowed_leverage"] == 0
    assert decision["recommended_leverage"] is None
    assert "allowed_leverage_below_minimum" in decision["cap_reasons_json"]
