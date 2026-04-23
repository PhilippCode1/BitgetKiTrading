#!/usr/bin/env python3
"""Benchmark: Python-Referenz vs. ``apex_core`` (Rust) für ATR/RSI/Trend.

Empfohlene Ausführung (Repo-Root)::

    PYTHONPATH=services/feature-engine/src:shared/python/src python scripts/benchmark_rust_vs_python_indicators.py

In Docker (gebautes ``feature-engine``-Image)::

    docker run --rm -v \"$PWD/scripts:/scripts:ro\" -w /app/services/feature-engine \\
      -e PYTHONPATH=/app:/app/shared/python/src \\
      bitget-ai-feature-engine-rust-test python /scripts/benchmark_rust_vs_python_indicators.py

Mit ``ENFORCE_RUST_SPEEDUP=1`` schlägt das Skript fehl, wenn der Median-Speedup < 5x ist.
"""

from __future__ import annotations

import math
import os
import statistics
import sys
import time
from math import isclose

import numpy as np

try:
    import apex_core
except ImportError:
    apex_core = None  # type: ignore[assignment]

from feature_engine.features.atr import OHLC, atr_sma as py_atr_sma
from feature_engine.features.momentum import trend_snapshot as py_trend_snapshot
from feature_engine.features.rsi import rsi_sma as py_rsi_sma


def _median_time(fn, *, repeats: int, warmup: int) -> float:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return float(statistics.median(samples))


def main() -> int:
    if apex_core is None:
        print("apex_core nicht installiert — Benchmark übersprungen.", file=sys.stderr)
        return 0

    n = 25_000
    window = 14
    rng = np.random.default_rng(7)
    drift = rng.standard_normal(n).astype(np.float64)
    closes = (100.0 + np.cumsum(drift)).astype(np.float64)
    highs = (closes + rng.random(n).astype(np.float64) * 0.5).astype(np.float64)
    lows = (closes - rng.random(n).astype(np.float64) * 0.5).astype(np.float64)
    opens = np.roll(closes, 1)
    opens[0] = closes[0]

    ohlc = [OHLC(o=float(o), h=float(h), l=float(l), c=float(c)) for o, h, l, c in zip(opens, highs, lows, closes, strict=False)]
    o64 = np.asarray(opens, dtype=np.float64, order="C")
    h64 = np.asarray(highs, dtype=np.float64, order="C")
    l64 = np.asarray(lows, dtype=np.float64, order="C")
    c64 = np.asarray(closes, dtype=np.float64, order="C")
    closes_list = closes.tolist()

    # Korrektheit (grobe Übereinstimmung; deterministische Seeds sollten 1e-9 liefern)
    atr_py = py_atr_sma(ohlc, window)
    atr_rs = float(apex_core.compute_atr_sma(o64, h64, l64, c64, window))
    if not (math.isnan(atr_py) and math.isnan(atr_rs)) and not isclose(atr_py, atr_rs, rel_tol=0.0, abs_tol=1e-9):
        print("ATR mismatch", atr_py, atr_rs, file=sys.stderr)
        return 2

    rsi_py = py_rsi_sma(closes_list, window)
    rsi_rs = float(apex_core.compute_rsi_sma(c64, window))
    if not (math.isnan(rsi_py) and math.isnan(rsi_rs)) and not isclose(rsi_py, rsi_rs, rel_tol=0.0, abs_tol=1e-9):
        print("RSI mismatch", rsi_py, rsi_rs, file=sys.stderr)
        return 2

    tr_py = py_trend_snapshot(closes_list)
    tr_rs = apex_core.compute_trend_snapshot(c64, 12, 26, 3)
    if not isclose(float(tr_rs[0]), tr_py.ema_fast, rel_tol=0.0, abs_tol=1e-9):
        print("Trend ema_fast mismatch", tr_rs[0], tr_py.ema_fast, file=sys.stderr)
        return 2

    repeats = 11
    warmup = 2

    t_py_atr = _median_time(lambda: py_atr_sma(ohlc, window), repeats=repeats, warmup=warmup)
    t_rs_atr = _median_time(lambda: apex_core.compute_atr_sma(o64, h64, l64, c64, window), repeats=repeats, warmup=warmup)

    t_py_rsi = _median_time(lambda: py_rsi_sma(closes_list, window), repeats=repeats, warmup=warmup)
    t_rs_rsi = _median_time(lambda: apex_core.compute_rsi_sma(c64, window), repeats=repeats, warmup=warmup)

    t_py_tr = _median_time(lambda: py_trend_snapshot(closes_list), repeats=repeats, warmup=warmup)
    t_rs_tr = _median_time(lambda: apex_core.compute_trend_snapshot(c64, 12, 26, 3), repeats=repeats, warmup=warmup)

    def ratio(py_t: float, rs_t: float) -> float:
        return py_t / rs_t if rs_t > 0 else float("inf")

    r_atr = ratio(t_py_atr, t_rs_atr)
    r_rsi = ratio(t_py_rsi, t_rs_rsi)
    r_tr = ratio(t_py_tr, t_rs_tr)

    print(f"n={n} window={window} repeats={repeats} (Medianzeit je Aufruf, s)")
    print(f"ATR  py={t_py_atr:.6f} rs={t_rs_atr:.6f} speedup={r_atr:.2f}x")
    print(f"RSI  py={t_py_rsi:.6f} rs={t_rs_rsi:.6f} speedup={r_rsi:.2f}x")
    print(f"TREND py={t_py_tr:.6f} rs={t_rs_tr:.6f} speedup={r_tr:.2f}x")

    min_speedup = min(r_atr, r_rsi, r_tr)
    if os.environ.get("ENFORCE_RUST_SPEEDUP") == "1" and min_speedup < 5.0:
        print(f"Speedup {min_speedup:.2f}x < 5x — fehlgeschlagen.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
