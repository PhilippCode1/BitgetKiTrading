from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.labeling.labels import compute_trade_targets


def _end_ts(path: list[dict], default: int = 999_999_999) -> int:
    if not path:
        return default
    return max(int(c["start_ts_ms"]) for c in path)


def test_trade_targets_distinguish_gross_and_net_returns() -> None:
    path = [
        {"start_ts_ms": 60_000, "high": "104", "low": "99.5"},
        {"start_ts_ms": 120_000, "high": "103.5", "low": "100.5"},
    ]
    out = compute_trade_targets(
        side="long",
        state="closed",
        decision_ts_ms=60_000,
        opened_ts_ms=60_000,
        evaluation_end_ts_ms=_end_ts(path),
        qty_base=Decimal("1"),
        entry_price_avg=Decimal("101"),
        exit_price_avg=Decimal("102"),
        pnl_net_usdt=Decimal("0.25"),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("103"),
        path_candles=path,
        isolated_margin=Decimal("20"),
        fees_total_usdt=Decimal("0.5"),
        funding_total_usdt=Decimal("-0.25"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
        market_regime="trend",
        stop_price=Decimal("98"),
    )
    targets = out.labels
    assert targets.take_trade_label is True
    assert targets.liquidation_risk is False
    assert float(targets.expected_return_gross_bps) == 300.0
    assert float(targets.expected_return_bps) == 25.0
    assert float(targets.expected_mfe_bps) == 400.0
    assert float(targets.expected_mae_bps) == 50.0
    assert round(float(targets.slippage_bps_entry or Decimal("0")), 6) == 100.0
    assert round(float(targets.slippage_bps_exit or Decimal("0")), 6) == 97.087379
    assert targets.liquidation_proximity_bps is not None
    assert float(targets.liquidation_proximity_bps) > 1200.0
    assert out.audit["evaluation_window"]["evaluation_end_ts_ms"] == _end_ts(path)
    assert out.audit["regime_stratification"]["regime"] == "trend"
    assert out.audit["risk_proximity"]["policy_stop_proximity_bps"] is not None


def test_trade_targets_flag_liquidation_risk_when_path_breaches_threshold() -> None:
    path = [{"start_ts_ms": 60_000, "high": "101", "low": "95"}]
    out = compute_trade_targets(
        side="long",
        state="closed",
        decision_ts_ms=60_000,
        opened_ts_ms=60_000,
        evaluation_end_ts_ms=_end_ts(path),
        qty_base=Decimal("1"),
        entry_price_avg=Decimal("100"),
        exit_price_avg=Decimal("97"),
        pnl_net_usdt=Decimal("-3"),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("97"),
        path_candles=path,
        isolated_margin=Decimal("10"),
        fees_total_usdt=Decimal("0"),
        funding_total_usdt=Decimal("0"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
    )
    targets = out.labels
    assert targets.take_trade_label is False
    assert targets.liquidation_risk is True
    assert targets.liquidation_proximity_bps == Decimal("0")


def test_trade_targets_ignore_candles_before_decision_anchor() -> None:
    path = [
        {"start_ts_ms": 60_000, "high": "120", "low": "80"},
        {"start_ts_ms": 120_000, "high": "102", "low": "99"},
    ]
    out = compute_trade_targets(
        side="long",
        state="closed",
        decision_ts_ms=120_000,
        opened_ts_ms=120_000,
        evaluation_end_ts_ms=_end_ts(path),
        qty_base=Decimal("1"),
        entry_price_avg=Decimal("100"),
        exit_price_avg=Decimal("101"),
        pnl_net_usdt=Decimal("1"),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("101"),
        path_candles=path,
        isolated_margin=Decimal("30"),
        fees_total_usdt=Decimal("0.1"),
        funding_total_usdt=Decimal("0"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
    )
    assert float(out.labels.expected_mfe_bps) == 200.0
    assert float(out.labels.expected_mae_bps) == 100.0
    assert out.audit["evaluation_window"]["candles_in_window"] == 1


def test_trade_targets_drop_future_candles_and_record_issue() -> None:
    path = [
        {"start_ts_ms": 60_000, "high": "101", "low": "99"},
        {"start_ts_ms": 500_000, "high": "200", "low": "50"},
    ]
    out = compute_trade_targets(
        side="long",
        state="closed",
        decision_ts_ms=60_000,
        opened_ts_ms=60_000,
        evaluation_end_ts_ms=120_000,
        qty_base=Decimal("1"),
        entry_price_avg=Decimal("100"),
        exit_price_avg=Decimal("100"),
        pnl_net_usdt=Decimal("0"),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("100"),
        path_candles=path,
        isolated_margin=Decimal("50"),
        fees_total_usdt=Decimal("0"),
        funding_total_usdt=Decimal("0"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
    )
    assert "candle_start_after_evaluation_end" in out.audit["window_issues"]
    assert out.audit["evaluation_window"]["candles_in_window"] == 1
    assert float(out.labels.expected_mfe_bps) == 100.0
    assert float(out.labels.expected_mae_bps) == 100.0


def test_evaluation_end_before_decision_yields_empty_path() -> None:
    out = compute_trade_targets(
        side="long",
        state="closed",
        decision_ts_ms=200_000,
        opened_ts_ms=200_000,
        evaluation_end_ts_ms=100_000,
        qty_base=Decimal("1"),
        entry_price_avg=Decimal("100"),
        exit_price_avg=Decimal("100"),
        pnl_net_usdt=Decimal("0"),
        entry_reference_price=Decimal("100"),
        exit_reference_price=Decimal("100"),
        path_candles=[{"start_ts_ms": 150_000, "high": "110", "low": "90"}],
        isolated_margin=Decimal("50"),
        fees_total_usdt=Decimal("0"),
        funding_total_usdt=Decimal("0"),
        maintenance_margin_rate=Decimal("0.005"),
        liq_fee_buffer_usdt=Decimal("5"),
    )
    assert "evaluation_end_before_decision" in out.audit["window_issues"]
    assert out.audit["evaluation_window"]["candles_in_window"] == 0
