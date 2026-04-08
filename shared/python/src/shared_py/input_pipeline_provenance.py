"""
Gemeinsame Metadaten fuer Feature-, Structure- und Drawing-Pipeline.

Liefert konsistente Luecken-Analyse auf sortierten Bar-Start-Timestamps,
Warmup-Flags und JSON-serialisierbare Provenance-Bundles fuer Downstream-Consumer.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
}

PIPELINE_PROVENANCE_VERSION = "1.0"


def timeframe_to_ms(timeframe: str) -> int:
    try:
        return TIMEFRAME_TO_MS[timeframe]
    except KeyError as e:
        raise ValueError(f"unsupported timeframe: {timeframe}") from e


def analyze_sorted_candle_starts(
    sorted_unique_start_ts_ms: Sequence[int],
    *,
    step_ms: int,
) -> dict[str, int]:
    """
    Erwartet aufsteigend sortierte, eindeutige start_ts_ms.
    Zaehmt fehlende Bars zwischen aufeinanderfolgenden Oeffnungen:
    delta/step_ms - 1 (0 bei exakt einem Schritt).
    """
    n = len(sorted_unique_start_ts_ms)
    if n <= 1:
        return {
            "bar_count": n,
            "expected_step_ms": step_ms,
            "max_gap_bars": 0,
            "gaps_ge_1_bar_count": 0,
            "total_missing_bars_estimate": 0,
        }
    max_gap = 0
    gaps_ge_1 = 0
    total_missing = 0
    for i in range(1, n):
        delta = int(sorted_unique_start_ts_ms[i]) - int(sorted_unique_start_ts_ms[i - 1])
        if delta < step_ms:
            continue
        extra = (delta // step_ms) - 1
        if extra > 0:
            gaps_ge_1 += 1
            total_missing += extra
            max_gap = max(max_gap, extra)
    return {
        "bar_count": n,
        "expected_step_ms": step_ms,
        "max_gap_bars": max_gap,
        "gaps_ge_1_bar_count": gaps_ge_1,
        "total_missing_bars_estimate": total_missing,
    }


def coverage_ok(max_gap_bars: int, *, max_allowed_gap_bars: int) -> bool:
    return max_gap_bars <= max_allowed_gap_bars


def feature_warmup_flags(
    bar_count: int,
    *,
    rsi_window: int,
    atr_window: int,
    vol_z_window: int,
) -> dict[str, bool]:
    return {
        "rsi_warmup_ok": bar_count >= rsi_window + 1,
        "atr_warmup_ok": bar_count >= atr_window + 1,
        "vol_z_warmup_ok": bar_count >= vol_z_window + 1,
    }


def realized_vol_std_log_returns(closes: Sequence[float], window: int = 20) -> float | None:
    """Std.dev der Log-Renditen ueber die letzten `window` Returns (window+1 Closes)."""
    if len(closes) < window + 1:
        return None
    segment = closes[-(window + 1) :]
    rets: list[float] = []
    for i in range(1, len(segment)):
        a, b = segment[i - 1], segment[i]
        if a <= 0 or b <= 0:
            return None
        rets.append(math.log(b / a))
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    if var < 0:
        return None
    return math.sqrt(var)


def build_feature_input_provenance(
    *,
    symbol: str,
    timeframe: str,
    sorted_bar_starts_ms: Sequence[int],
    bar_close_ts_ms: int,
    max_allowed_gap_bars: int,
    rsi_window: int,
    atr_window: int,
    vol_z_window: int,
    source_event_id: str,
    computed_ts_ms: int,
    feature_schema_version: str,
    feature_schema_hash: str,
    analysis_ts_ms: int,
    ret_10: float | None,
    realized_vol_20: float | None,
    auxiliary_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    step = timeframe_to_ms(timeframe)
    gap = analyze_sorted_candle_starts(sorted_bar_starts_ms, step_ms=step)
    max_gap = int(gap["max_gap_bars"])
    cov = coverage_ok(max_gap, max_allowed_gap_bars=max_allowed_gap_bars)
    warm = feature_warmup_flags(
        int(gap["bar_count"]),
        rsi_window=rsi_window,
        atr_window=atr_window,
        vol_z_window=vol_z_window,
    )
    core_complete = cov and all(warm.values())
    out: dict[str, Any] = {
        "pipeline_version": PIPELINE_PROVENANCE_VERSION,
        "stage": "feature",
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_close_ts_ms": bar_close_ts_ms,
        "analysis_ts_ms": analysis_ts_ms,
        "computed_ts_ms": computed_ts_ms,
        "source_event_id": source_event_id,
        "feature_schema_version": feature_schema_version,
        "feature_schema_hash": feature_schema_hash,
        "candle_series": {
            **gap,
            "coverage_ok": cov,
            "max_allowed_gap_bars": max_allowed_gap_bars,
        },
        "warmup": warm,
        "feature_core_complete": core_complete,
        "signals": {},
    }
    if ret_10 is not None and not (math.isnan(ret_10) or math.isinf(ret_10)):
        out["signals"]["ret_10"] = float(ret_10)
    if realized_vol_20 is not None and not (math.isnan(realized_vol_20) or math.isinf(realized_vol_20)):
        out["signals"]["realized_vol_logret_20"] = float(realized_vol_20)
    if auxiliary_inputs:
        out["auxiliary_inputs"] = dict(auxiliary_inputs)
    return out


def build_structure_input_provenance(
    *,
    symbol: str,
    timeframe: str,
    sorted_bar_starts_ms: Sequence[int],
    bar_close_ts_ms: int,
    max_allowed_gap_bars: int,
    bos_choch_max_gap_bars: int,
    structure_lookback_bars: int,
    updated_ts_ms: int,
    source_event_id: str,
    bos_choch_suppressed: bool,
    false_breakout_watch_enabled: bool,
) -> dict[str, Any]:
    step = timeframe_to_ms(timeframe)
    gap = analyze_sorted_candle_starts(sorted_bar_starts_ms, step_ms=step)
    max_gap = int(gap["max_gap_bars"])
    cov = coverage_ok(max_gap, max_allowed_gap_bars=max_allowed_gap_bars)
    bos_choch_allowed = coverage_ok(max_gap, max_allowed_gap_bars=bos_choch_max_gap_bars)
    return {
        "pipeline_version": PIPELINE_PROVENANCE_VERSION,
        "stage": "structure",
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_close_ts_ms": bar_close_ts_ms,
        "updated_ts_ms": updated_ts_ms,
        "source_event_id": source_event_id,
        "structure_lookback_bars": structure_lookback_bars,
        "candle_series": {
            **gap,
            "coverage_ok": cov,
            "max_allowed_gap_bars": max_allowed_gap_bars,
        },
        "gates": {
            "bos_choch_allowed": bos_choch_allowed,
            "bos_choch_suppressed": bos_choch_suppressed,
            "false_breakout_watch_enabled": false_breakout_watch_enabled,
            "bos_choch_max_gap_bars": bos_choch_max_gap_bars,
        },
    }


def build_drawing_input_provenance(
    *,
    symbol: str,
    timeframe: str,
    structure_bar_ts_ms: int,
    structure_state_updated_ts_ms: int | None,
    structure_provenance: Mapping[str, Any] | None,
    orderbook_ts_ms: int | None,
    drawing_computed_ts_ms: int,
    orderbook_max_age_ms: int,
    orderbook_fresh: bool,
) -> dict[str, Any]:
    ob_age: int | None = None
    if orderbook_ts_ms is not None:
        ob_age = max(0, drawing_computed_ts_ms - int(orderbook_ts_ms))
    sp = dict(structure_provenance) if structure_provenance else {}
    cs = sp.get("candle_series") if isinstance(sp.get("candle_series"), dict) else {}
    return {
        "pipeline_version": PIPELINE_PROVENANCE_VERSION,
        "stage": "drawing",
        "symbol": symbol,
        "timeframe": timeframe,
        "structure_bar_ts_ms": structure_bar_ts_ms,
        "structure_state_updated_ts_ms": structure_state_updated_ts_ms,
        "drawing_computed_ts_ms": drawing_computed_ts_ms,
        "orderbook": {
            "latest_ts_ms": orderbook_ts_ms,
            "age_ms_at_draw": ob_age,
            "max_allowed_age_ms": orderbook_max_age_ms,
            "fresh": orderbook_fresh,
        },
        "inherited_structure_candle_series": cs,
    }
