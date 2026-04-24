from __future__ import annotations

from decimal import Decimal

from shared_py.post_trade_review import (
    classify_reasoning_quality,
    evaluate_thesis_vs_candles,
    extract_reference_level_from_strategy_result,
)


def test_lucky_wrong_classify() -> None:
    l, a = classify_reasoning_quality(
        pnl_net=Decimal("10"), thesis_holds=False
    )
    assert l == "lucky_wrong_reasoning"
    assert a < 0.5


def test_support_held_long() -> None:
    ref = 100.0
    candles = [
        {"low": 100.1, "high": 101.0},
        {"low": 100.2, "high": 101.2},
    ]
    h, _ = evaluate_thesis_vs_candles(
        side="long",
        reference_price=ref,
        role="support",
        candles=candles,
    )
    assert h is True


def test_extract_from_chart_annotations() -> None:
    r = {
        "expected_scenario_de": "",
        "chart_annotations": {
            "schema_version": "1.0",
            "horizontal_lines": [{"price": 65000, "label": "Support"}],
        },
    }
    p, src, role = extract_reference_level_from_strategy_result(r)
    assert p == 65000.0
    assert "chart" in src
    assert role in ("support", "unknown", "resistance")
