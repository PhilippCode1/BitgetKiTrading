from __future__ import annotations

import base64
import math
import time
from typing import Any

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

from adversarial_engine.arrow_ipc import encode_table_ipc_stream
from adversarial_engine.config import AdversarialEngineSettings
from adversarial_engine.market_stresser import build_stress_tick_table, tensor_paths_to_numpy
from adversarial_engine.models.wgan_gp import AdversarialMarketSimulator


def _moments(x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if x.size < 4:
        return {"skewness": 0.0, "kurtosis_excess": 0.0}
    m = float(x.mean())
    s = float(x.std(ddof=1)) or 1e-12
    skew = float(np.mean(((x - m) / s) ** 3))
    kurt = float(np.mean(((x - m) / s) ** 4) - 3.0)
    return {"skewness": skew, "kurtosis_excess": kurt}


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    if a.size != b.size or a.size < 4:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


class ToxicBatchRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=64)
    seq_len: int = Field(default=128, ge=32, le=2048)
    toxicity_0_1: float = Field(default=0.65, ge=0.0, le=1.0)
    batch: int = Field(default=1, ge=1, le=16)
    anchor_price: float = Field(default=95_000.0, gt=0.0)
    ts_start_ms: int | None = Field(default=None, ge=0)
    step_ms: int = Field(default=250, ge=50, le=60_000)
    seed: int | None = None
    price_depth_rho: float | None = Field(default=None, ge=-0.95, le=0.95)
    return_arrow: bool = Field(default=True)


class ToxicBatchResponse(BaseModel):
    schema_version: str = "ams_toxic_tick_batch_v1"
    symbol: str
    rows: int
    toxicity_0_1: float
    moments: dict[str, Any]
    arrow_ipc_b64: str | None = None


def build_router(settings: AdversarialEngineSettings) -> APIRouter:
    r = APIRouter(tags=["adversarial"])
    _sim: AdversarialMarketSimulator | None = None

    def _get_sim(seq_len: int) -> AdversarialMarketSimulator:
        nonlocal _sim
        if _sim is None or _sim.seq_len != int(seq_len):
            _sim = AdversarialMarketSimulator(
                latent_dim=int(settings.ams_latent_dim),
                seq_len=int(seq_len),
                rho=float(settings.ams_price_depth_rho),
                checkpoint_path=settings.ams_checkpoint_path,
            )
        return _sim

    @r.post("/ams/v1/toxic-batch", response_model=ToxicBatchResponse)
    def toxic_batch(body: ToxicBatchRequest) -> ToxicBatchResponse:
        sim = _get_sim(body.seq_len)
        paths, meta = sim.generate_paths(
            batch=int(body.batch),
            toxicity_0_1=float(body.toxicity_0_1),
            seed=body.seed,
            rho=body.price_depth_rho,
        )
        r_np, d_np = tensor_paths_to_numpy(paths)
        ts0 = int(body.ts_start_ms) if body.ts_start_ms is not None else int(time.time() * 1000)
        table = build_stress_tick_table(
            r_np,
            d_np,
            symbol=body.symbol,
            anchor_price=float(body.anchor_price),
            ts_start_ms=ts0,
            step_ms=int(body.step_ms),
            toxicity=float(body.toxicity_0_1),
        )
        moments = {
            "log_return": _moments(r_np),
            "depth_imbalance": _moments(d_np),
            "price_depth_corr": _pearson(r_np, d_np),
            "meta": meta,
        }
        b64: str | None = None
        if body.return_arrow:
            raw = encode_table_ipc_stream(table)
            b64 = base64.standard_b64encode(raw).decode("ascii")
        return ToxicBatchResponse(
            symbol=body.symbol.upper(),
            rows=int(table.num_rows),
            toxicity_0_1=float(body.toxicity_0_1),
            moments=moments,
            arrow_ipc_b64=b64,
        )

    @r.get("/ams/v1/reference-extreme-profile")
    def reference_extreme_profile() -> dict[str, Any]:
        """Statistisches Referenzprofil (deterministisch) fuer Validierungsskripte."""
        t = np.linspace(0.0, 1.0, 256, dtype=np.float64)
        mid = np.exp(-((t - 0.52) ** 2) / (2 * 0.07**2))
        r = -2.8 * mid * np.sin(5 * math.pi * t)
        d = -1.6 * np.sin(math.pi * t) ** 3
        return {
            "schema": "ams_reference_extreme_v1",
            "moments": {"log_return": _moments(r), "depth_imbalance": _moments(d), "corr": _pearson(r, d)},
        }

    return r


def build_health_router(settings: AdversarialEngineSettings) -> APIRouter:
    hr = APIRouter(tags=["health"])

    @hr.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "adversarial-engine"}

    @hr.get("/ready")
    def ready() -> dict[str, Any]:
        return {"ready": True, "port": int(settings.adversarial_engine_port)}

    return hr
