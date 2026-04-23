from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator

import grpc
import numpy as np
from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2 as pb2
from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2_grpc as pb2_grpc

from inference_server.config import InferenceServerSettings
from inference_server.monitoring import schedule_batch_metric_report
from inference_server.timesfm_model import TimesFmModelEngine


def _decode_series(ts: pb2.TimeSeries) -> np.ndarray | None:
    if ts.length <= 0:
        return np.array([], dtype=np.float32)
    need = int(ts.length) * 4
    raw = ts.values_f32_le
    if len(raw) != need:
        return None
    return np.frombuffer(raw, dtype=np.float32, count=int(ts.length)).copy()


class TimesFmInferenceServicer(pb2_grpc.TimesFmInferenceServicer):
    def __init__(self, settings: InferenceServerSettings, engine: TimesFmModelEngine) -> None:
        self._settings = settings
        self._engine = engine
        self._sem = asyncio.Semaphore(settings.timesfm_max_inflight_batches)
        self._stream_windows: dict[str, list[float]] = defaultdict(list)

    async def PredictBatch(self, request: pb2.PredictBatchRequest, context: grpc.aio.ServicerContext) -> pb2.PredictBatchResponse:  # type: ignore[name-defined]
        try:
            await asyncio.wait_for(
                self._sem.acquire(),
                timeout=self._settings.timesfm_batch_semaphore_wait_sec,
            )
        except asyncio.TimeoutError:
            await context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                "inference-server: batch limit / semaphore timeout",
            )
            raise
        t0 = time.perf_counter()
        try:
            arrays: list[np.ndarray] = []
            for ts in request.series:
                arr = _decode_series(ts)
                if arr is None:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        f"series length/bytes mismatch for asset_id={ts.asset_id!r}",
                    )
                    raise RuntimeError("abort")
                arrays.append(arr)
            horizon = int(request.forecast_horizon) if request.forecast_horizon else 16
            horizon = max(1, min(horizon, 512))
            preds = self._engine.predict_batch(arrays, horizon=horizon)
            forecasts: list[pb2.ForecastTensor] = []
            for ts, fc in zip(request.series, preds, strict=True):
                f32 = np.asarray(fc, dtype=np.float32).reshape(-1)
                forecasts.append(
                    pb2.ForecastTensor(
                        asset_id=ts.asset_id,
                        forecast_f32_le=f32.tobytes(),
                        horizon=int(f32.size),
                    )
                )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            schedule_batch_metric_report(
                self._settings,
                batch_size=len(request.series),
                forecast_horizon=horizon,
                latency_ms=latency_ms,
                backend=self._engine.backend_name,
            )
            mid = request.model_id or self._settings.timesfm_model_id
            return pb2.PredictBatchResponse(
                forecasts=forecasts,
                backend=self._engine.backend_name,
                model_id=mid[:200],
            )
        finally:
            self._sem.release()

    async def StreamTicks(
        self,
        request_iterator: AsyncIterator[pb2.TickFrame],
        context: grpc.aio.ServicerContext,  # type: ignore[name-defined]
    ) -> AsyncIterator[pb2.PredictionFrame]:
        horizon = 8
        async for tick in request_iterator:
            w = self._stream_windows[tick.asset_id]
            w.append(float(tick.price))
            del w[:-128]
            arr = np.asarray(w, dtype=np.float32)
            t0 = time.perf_counter()
            fc = self._engine.predict_batch([arr], horizon=horizon)[0]
            latency_ms = (time.perf_counter() - t0) * 1000.0
            schedule_batch_metric_report(
                self._settings,
                batch_size=1,
                forecast_horizon=horizon,
                latency_ms=latency_ms,
                backend=self._engine.backend_name,
            )
            f32 = np.asarray(fc, dtype=np.float32).reshape(-1)
            yield pb2.PredictionFrame(
                asset_id=tick.asset_id,
                point_forecast_f32_le=f32.tobytes(),
                horizon=int(f32.size),
                computed_ts_ms=int(time.time() * 1000),
                backend=self._engine.backend_name,
            )
