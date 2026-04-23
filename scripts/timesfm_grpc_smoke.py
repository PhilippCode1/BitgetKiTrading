#!/usr/bin/env python3
"""
Smoke-Test: gRPC PredictBatch gegen inference-server (lokal oder Docker).

Beispiele::

    # Host mit local-publish (Ports 8140 / 50051)
    python scripts/timesfm_grpc_smoke.py --target 127.0.0.1:50051

    # Nur im Compose-Netz (aus einem Worker-Container)
    python scripts/timesfm_grpc_smoke.py --target inference-server:50051
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_paths() -> None:
    root = _repo_root()
    for rel in ("shared/python/src",):
        p = root / rel
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


async def _run(target: str, horizon: int) -> int:
    import numpy as np

    from shared_py.timesfm_client import TimesFmGrpcClient

    rng = np.random.default_rng(0)
    x = np.cumsum(rng.normal(0.0, 0.001, size=128)).astype(np.float32) + 50_000.0

    async with TimesFmGrpcClient(target) as client:
        ys = await client.predict_batch(
            [("BTCUSDT", x), ("ETHUSDT", x * 0.99)],
            forecast_horizon=horizon,
            model_id="google/timesfm-1.0-200m",
        )
    print("forecasts:", len(ys), "shapes:", [y.shape for y in ys])
    print("BTC head:", ys[0][: min(5, ys[0].size)])
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="TimesFM gRPC PredictBatch smoke")
    p.add_argument(
        "--target",
        default="127.0.0.1:50051",
        help="gRPC-Ziel host:port (Compose: inference-server:50051)",
    )
    p.add_argument("--horizon", type=int, default=12)
    args = p.parse_args()
    _ensure_paths()
    return asyncio.run(_run(args.target, args.horizon))


if __name__ == "__main__":
    raise SystemExit(main())
