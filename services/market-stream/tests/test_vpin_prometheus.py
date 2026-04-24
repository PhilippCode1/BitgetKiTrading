from __future__ import annotations

import time

from prometheus_client import REGISTRY, generate_latest
from shared_py.observability.metrics import (
    observe_market_vpin_inference,
    set_market_vpin_score,
)
from shared_py.rust_core_bridge import APEX_CORE_AVAILABLE, get_vpin_engine_class


def test_market_vpin_score_exposed_in_textformat() -> None:
    set_market_vpin_score(symbol="TESTUSDT", score=0.42)
    raw = generate_latest(REGISTRY)
    text = raw.decode("utf-8", errors="replace")
    assert "market_vpin_score" in text
    assert 'symbol="TESTUSDT"' in text or "symbol='TESTUSDT'" in text


def test_vpin_rust_path_under_5ms() -> None:
    """
    SLO: on_trades-Batch; Rust push+toxicity bleibt typisch <5ms;
    kleiner Batch fuer deterministische CI.
    """
    Vpin = get_vpin_engine_class()
    if Vpin is None or not APEX_CORE_AVAILABLE:
        return
    eng = Vpin(10.0, 30)
    t0 = time.perf_counter()
    for i in range(16):
        eng.push_trade(100.0 + (i % 3) * 0.01, 0.1, i % 2 == 0)
    _ = eng.toxicity_score()
    dt = time.perf_counter() - t0
    msg = f"VPIN (Rust) batch <5ms, war {dt*1000:.3f}ms"
    assert dt < 0.005, msg
    observe_market_vpin_inference(
        symbol="LATTEST", duration_sec=dt, slow_threshold_sec=0.005
    )
    out = generate_latest(REGISTRY).decode("utf-8", errors="replace")
    assert "market_vpin_inference_duration_seconds" in out
