"""
Asynchroner gRPC-Client fuer den Apex ``TimesFmInference``-Dienst (TimesFM / Stub-Backend).

Benötigt ``grpcio`` (z. B. ``pip install "shared-py[grpc]"`` aus ``shared/python``).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from shared_py.resilience import CircuitBreaker

if TYPE_CHECKING:
    import grpc

try:
    import grpc as _grpc
except ImportError as exc:  # pragma: no cover
    _grpc = None  # type: ignore[assignment]
    _GRPC_IMPORT_ERROR = exc
else:
    _GRPC_IMPORT_ERROR = None

if _grpc is not None:
    _CB_FAIL_CODES: frozenset[Any] = frozenset(
        {
            _grpc.StatusCode.RESOURCE_EXHAUSTED,
            _grpc.StatusCode.UNAVAILABLE,
            _grpc.StatusCode.DEADLINE_EXCEEDED,
            _grpc.StatusCode.ABORTED,
        }
    )
else:
    _CB_FAIL_CODES = frozenset()


def _load_pb() -> tuple[Any, Any]:
    from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2 as pb2
    from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2_grpc as pb2_grpc

    return pb2, pb2_grpc


def _encode_series(pb2: Any, asset_id: str, arr: np.ndarray) -> Any:
    a = np.asarray(arr, dtype=np.float32).reshape(-1)
    return pb2.TimeSeries(
        asset_id=asset_id,
        length=int(a.size),
        values_f32_le=a.tobytes(),
    )


class TimesFmGrpcClient:
    """
    gRPC-aio Client mit einfachem Circuit Breaker (Oeffnung bei Ueberlast / Transportfehlern).

    Beispiel::

        async with TimesFmGrpcClient("inference-server:50051") as client:
            y = await client.predict_batch([("BTCUSDT", x)], forecast_horizon=8)
    """

    def __init__(
        self,
        target: str,
        *,
        circuit_breaker: CircuitBreaker | None = None,
        circuit_key: str = "timesfm_grpc",
    ) -> None:
        if _grpc is None:
            raise ImportError(
                "grpcio fehlt — bitte installieren (z. B. pip install grpcio)."
            ) from _GRPC_IMPORT_ERROR
        self._target = target
        self._grpc_aio = __import__("grpc.aio", fromlist=["aio"])
        self._channel: Any = None
        self._stub: Any = None
        self._cb = circuit_breaker or CircuitBreaker(fail_threshold=4, open_seconds=45)
        self._circuit_key = circuit_key

    async def __aenter__(self) -> TimesFmGrpcClient:
        _, pb2_grpc = _load_pb()
        self._channel = self._grpc_aio.insecure_channel(self._target)
        self._stub = pb2_grpc.TimesFmInferenceStub(self._channel)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._channel is not None:
            await self._channel.close()
        self._channel = None
        self._stub = None

    async def predict_batch(
        self,
        series: Sequence[tuple[str, np.ndarray]],
        *,
        forecast_horizon: int = 16,
        model_id: str = "",
        timeout_sec: float = 30.0,
    ) -> list[np.ndarray]:
        if self._stub is None:
            raise RuntimeError("TimesFmGrpcClient: vorher async with / connect verwenden")
        if self._cb.is_open(self._circuit_key):
            raise RuntimeError("timesfm_grpc_circuit_open")
        pb2, _pb2_grpc = _load_pb()
        req = pb2.PredictBatchRequest(
            series=[_encode_series(pb2, aid, arr) for aid, arr in series],
            forecast_horizon=int(forecast_horizon),
            model_id=model_id or "",
        )
        try:
            resp = await self._stub.PredictBatch(req, timeout=float(timeout_sec))
        except self._grpc_aio.AioRpcError as exc:
            if exc.code() in _CB_FAIL_CODES:
                self._cb.record_failure(self._circuit_key)
            raise
        self._cb.record_success(self._circuit_key)
        out: list[np.ndarray] = []
        for f in resp.forecasts:
            out.append(
                np.frombuffer(
                    f.forecast_f32_le,
                    dtype=np.float32,
                    count=int(f.horizon),
                ).copy()
            )
        return out

    async def stream_ticks(
        self,
        tick_source: AsyncIterator[Any],
        *,
        timeout_sec: float | None = None,
    ) -> AsyncIterator[Any]:
        if self._stub is None:
            raise RuntimeError("TimesFmGrpcClient: vorher async with / connect verwenden")
        if self._cb.is_open(self._circuit_key):
            raise RuntimeError("timesfm_grpc_circuit_open")
        call = self._stub.StreamTicks(tick_source, timeout=timeout_sec)
        try:
            async for frame in call:
                yield frame
        except self._grpc_aio.AioRpcError as exc:
            if exc.code() in _CB_FAIL_CODES:
                self._cb.record_failure(self._circuit_key)
            raise
        else:
            self._cb.record_success(self._circuit_key)


async def predict_batch_numpy(
    target: str,
    series: Sequence[tuple[str, np.ndarray]],
    *,
    forecast_horizon: int = 16,
    model_id: str = "",
    timeout_sec: float = 30.0,
) -> list[np.ndarray]:
    """Kurzform: ein Kanal pro Aufruf (fuer Skripte/Tests)."""
    async with TimesFmGrpcClient(target) as client:
        return await client.predict_batch(
            series,
            forecast_horizon=forecast_horizon,
            model_id=model_id,
            timeout_sec=timeout_sec,
        )


def predict_batch_numpy_sync(
    target: str,
    series: Sequence[tuple[str, np.ndarray]],
    *,
    forecast_horizon: int = 16,
    model_id: str = "",
    timeout_sec: float = 30.0,
) -> list[np.ndarray]:
    """Synchroner Wrapper fuer einfache CLI-/Testskripte."""
    return asyncio.run(
        predict_batch_numpy(
            target,
            series,
            forecast_horizon=forecast_horizon,
            model_id=model_id,
            timeout_sec=timeout_sec,
        )
    )
