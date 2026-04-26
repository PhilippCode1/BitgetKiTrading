from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FE_SRC = ROOT / "services" / "feature-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (FE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from feature_engine.tsfm_pipeline import (  # noqa: E402
    MAX_TICKS_PER_SYMBOL,
    TickBuffer,
    build_timesfm_context_vector,
    forecast_confidence_metrics,
    prepare_context_under_ms,
)


def test_tick_buffer_maxlen_and_tail() -> None:
    buf = TickBuffer(maxlen=10)
    for i in range(15):
        buf.append("BTCUSDT", 1000 + i, 50_000.0 + float(i) * 0.01)
    assert buf.last_gap_ms("BTCUSDT") == 1
    t = buf.tail_prices("BTCUSDT", 5)
    assert t is not None and t.shape == (5,)
    assert t[-1] > t[0]


def test_prepare_context_budget_smoke_for_full_buffer() -> None:
    # `coverage run` nutzt sys.settrace — dasselbe Budget ist unter Tracing unzuverlaessig.
    # Ohne Tracing: harte 5ms-Wand schlug auf langsamen/lastigen Hosts fehl (Flakes ~8–16ms).
    budget = 20.0
    max_wall_ms = 20.0
    if sys.gettrace() is not None:
        budget = 100.0
        max_wall_ms = 200.0
    buf = TickBuffer(maxlen=MAX_TICKS_PER_SYMBOL)
    base = 50_000.0
    rng = np.random.default_rng(42)
    for i in range(MAX_TICKS_PER_SYMBOL):
        ts = 1_700_000_000_000 + i * 50
        base += float(rng.normal(0, 0.05))
        buf.append("ETHUSDT", ts, base)
    # Einmaliger Warm-up stabilisiert NumPy-/Alloc-Pfade; danach messen wir die Latenz.
    prepare_context_under_ms(
        buf,
        "ETHUSDT",
        context_len=1024,
        rolling_z_window=256,
        use_numba=False,
        budget_ms=200.0,
    )
    t0 = time.perf_counter()
    vec, meta = prepare_context_under_ms(
        buf,
        "ETHUSDT",
        context_len=1024,
        rolling_z_window=256,
        use_numba=False,
        budget_ms=budget,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert vec.shape == (1024,)
    assert vec.dtype == np.float32
    assert meta["prepare_context_ms"] < budget
    assert elapsed_ms < max_wall_ms


def test_build_context_and_confidence() -> None:
    p = np.linspace(100.0, 101.0, 1025).astype(np.float64)
    v = build_timesfm_context_vector(p, context_len=1024, rolling_z_window=64, use_numba=False)
    assert v.shape == (1024,)
    m = forecast_confidence_metrics(np.linspace(1.0, 1.5, 80))
    assert 0.0 <= m["confidence_0_1"] <= 1.0


def test_predict_timesfm_patch_mocked() -> None:
    import asyncio

    from feature_engine import tsfm_pipeline as tp

    fake = np.arange(32, dtype=np.float32)

    async def _run() -> list[np.ndarray]:
        with patch.object(tp, "TimesFmGrpcClient") as m_client:
            inst = m_client.return_value
            inst.__aenter__ = AsyncMock(return_value=inst)
            inst.__aexit__ = AsyncMock(return_value=None)
            inst.predict_batch = AsyncMock(return_value=[fake])
            ctx = np.zeros(64, dtype=np.float32)
            return await tp.predict_timesfm_patch(
                "127.0.0.1:59999",
                ctx,
                forecast_horizon=32,
                model_id="test",
            )

    out = asyncio.run(_run())
    assert len(out) == 1
    np.testing.assert_array_equal(out[0], fake)
