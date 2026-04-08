from __future__ import annotations

import math

from shared_py.input_pipeline_provenance import (
    PIPELINE_PROVENANCE_VERSION,
    analyze_sorted_candle_starts,
    build_drawing_input_provenance,
    build_feature_input_provenance,
    build_structure_input_provenance,
    coverage_ok,
    realized_vol_std_log_returns,
    timeframe_to_ms,
)


def test_timeframe_to_ms_known() -> None:
    assert timeframe_to_ms("5m") == 300_000


def test_analyze_sorted_candles_contiguous_no_gaps() -> None:
    step = 60_000
    ts = [1_000_000 + i * step for i in range(5)]
    g = analyze_sorted_candle_starts(ts, step_ms=step)
    assert g["bar_count"] == 5
    assert g["max_gap_bars"] == 0
    assert g["gaps_ge_1_bar_count"] == 0


def test_analyze_sorted_candles_detects_two_missing_bars() -> None:
    step = 60_000
    base = 1_000_000
    ts = [base, base + step, base + 4 * step]
    g = analyze_sorted_candle_starts(ts, step_ms=step)
    assert g["max_gap_bars"] == 2
    assert g["total_missing_bars_estimate"] == 2


def test_coverage_ok_at_boundary() -> None:
    assert coverage_ok(2, max_allowed_gap_bars=2) is True
    assert coverage_ok(3, max_allowed_gap_bars=2) is False


def test_realized_vol_constant_series_is_zero() -> None:
    closes = [100.0] * 25
    v = realized_vol_std_log_returns(closes, window=20)
    assert v is not None
    assert v == 0.0


def test_realized_vol_insufficient_history() -> None:
    assert realized_vol_std_log_returns([1.0, 2.0], window=20) is None


def test_feature_provenance_flags_incomplete_warmup() -> None:
    step = 60_000
    ts = [1_000_000 + i * step for i in range(10)]
    p = build_feature_input_provenance(
        symbol="BTCUSDT",
        timeframe="1m",
        sorted_bar_starts_ms=ts,
        bar_close_ts_ms=ts[-1],
        max_allowed_gap_bars=3,
        rsi_window=14,
        atr_window=14,
        vol_z_window=50,
        source_event_id="e1",
        computed_ts_ms=2_000_000,
        feature_schema_version="2.0",
        feature_schema_hash="abc",
        analysis_ts_ms=2_000_000,
        ret_10=0.01,
        realized_vol_20=0.02,
        auxiliary_inputs={"orderbook_present": False},
    )
    assert p["pipeline_version"] == PIPELINE_PROVENANCE_VERSION
    assert p["candle_series"]["coverage_ok"] is True
    assert p["warmup"]["rsi_warmup_ok"] is False
    assert p["feature_core_complete"] is False
    assert p["signals"]["ret_10"] == 0.01
    assert not math.isnan(float(p["signals"]["realized_vol_logret_20"]))


def test_structure_provenance_bos_gate_independent_of_coverage_threshold() -> None:
    step = 300_000
    ts = [1_000_000 + i * step for i in range(8)]
    ts[4] = ts[3] + 3 * step
    g = analyze_sorted_candle_starts(ts, step_ms=step)
    assert g["max_gap_bars"] == 2
    p = build_structure_input_provenance(
        symbol="BTCUSDT",
        timeframe="5m",
        sorted_bar_starts_ms=ts,
        bar_close_ts_ms=ts[-1],
        max_allowed_gap_bars=3,
        bos_choch_max_gap_bars=1,
        structure_lookback_bars=len(ts),
        updated_ts_ms=9_000_000,
        source_event_id="e2",
        bos_choch_suppressed=True,
        false_breakout_watch_enabled=False,
    )
    assert p["candle_series"]["coverage_ok"] is True
    assert p["gates"]["bos_choch_allowed"] is False


def test_drawing_provenance_orderbook_age() -> None:
    d = build_drawing_input_provenance(
        symbol="BTCUSDT",
        timeframe="5m",
        structure_bar_ts_ms=1_000,
        structure_state_updated_ts_ms=2_000,
        structure_provenance={"candle_series": {"coverage_ok": True, "max_gap_bars": 0}},
        orderbook_ts_ms=7_000,
        drawing_computed_ts_ms=10_000,
        orderbook_max_age_ms=5_000,
        orderbook_fresh=True,
    )
    assert d["orderbook"]["age_ms_at_draw"] == 3_000
    assert d["inherited_structure_candle_series"]["max_gap_bars"] == 0
