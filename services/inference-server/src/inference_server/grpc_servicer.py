from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import grpc
import numpy as np
from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2 as pb2
from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2_grpc as pb2_grpc

from inference_server import inference_telemetry
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


@dataclass(frozen=True)
class _WorkItem:
    request: pb2.PredictBatchRequest
    context: Any
    arrays: list[np.ndarray]
    done: asyncio.Future[pb2.PredictBatchResponse]


class _DynamicBatcher:
    """
    Sammelt mehrere PredictBatch-gRPCs kurz (max_wait_ms / max_size) und fuehrt
    genau ein predict_batch (GPU) aus.
    """

    def __init__(
        self,
        *,
        servicer: TimesFmInferenceServicer,
        max_wait_ms: float,
        max_size: int,
    ) -> None:
        self._serv = servicer
        self._max_wait_s = max(0.0, float(max_wait_ms)) / 1000.0
        self._max_size = int(max(1, max_size))
        self._pending: list[_WorkItem] = []
        self._timer: Any | None = None
        self._flush_lock = asyncio.Lock()

    def _cancel_timer(self) -> None:
        t = self._timer
        self._timer = None
        if t is not None:
            try:
                t.cancel()
            except Exception:  # noqa: BLE001
                pass

    def _arm_timer(self) -> None:
        if self._max_wait_s <= 0 or self._timer is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        def _cb() -> None:
            self._timer = None
            asyncio.create_task(self._flush_safe())

        self._timer = loop.call_later(self._max_wait_s, _cb)

    def pending_count(self) -> int:
        return len(self._pending)

    async def _flush_safe(self) -> None:
        if self._flush_lock.locked():
            return
        try:
            async with self._flush_lock:
                await self._flush()
        except Exception as exc:  # noqa: BLE001
            for it in self._pending:
                if not it.done.done():
                    it.done.set_exception(RuntimeError(f"batch_flush_failed: {exc!s}"))
            self._pending.clear()
            self._cancel_timer()
            return

    async def _flush(self) -> None:
        if not self._pending:
            return
        work = self._pending
        self._pending = []
        self._cancel_timer()
        await self._serv._process_work_items(work)  # noqa: SLF001

    async def submit(
        self,
        *,
        request: pb2.PredictBatchRequest,
        context: Any,
        arrays: list[np.ndarray],
    ) -> pb2.PredictBatchResponse:
        loop = asyncio.get_running_loop()
        done: asyncio.Future[pb2.PredictBatchResponse] = loop.create_future()
        w = _WorkItem(request=request, context=context, arrays=arrays, done=done)
        self._pending.append(w)
        if len(self._pending) >= self._max_size:
            self._cancel_timer()
            await self._flush_safe()
        else:
            self._arm_timer()
        return await done


class TimesFmInferenceServicer(pb2_grpc.TimesFmInferenceServicer):
    def __init__(self, settings: InferenceServerSettings, engine: TimesFmModelEngine) -> None:
        self._settings = settings
        self._engine = engine
        self._sem = asyncio.Semaphore(settings.timesfm_max_inflight_batches)
        self._stream_windows: defaultdict[str, list[float]] = defaultdict(list)
        if settings.timesfm_dynamic_batching_enabled:
            self._batcher = _DynamicBatcher(
                servicer=self,
                max_wait_ms=settings.timesfm_dynamic_batch_max_wait_ms,
                max_size=settings.timesfm_dynamic_batch_max_size,
            )
        else:
            self._batcher = None

    def get_batch_buffer_depth(self) -> int:
        if self._batcher is None:
            return 0
        return int(self._batcher.pending_count())

    def _set_trailing(self, context: Any) -> None:
        try:
            context.set_trailing_metadata(inference_telemetry.trailing_metadata_tuples())
        except Exception:  # noqa: BLE001
            pass

    async def _process_work_items(self, work: list[_WorkItem]) -> None:
        try:
            await asyncio.wait_for(
                self._sem.acquire(),
                timeout=self._settings.timesfm_batch_semaphore_wait_sec,
            )
        except asyncio.TimeoutError as exc:
            for w in work:
                if not w.done.done():
                    w.done.set_exception(exc)
            return
        t0 = time.perf_counter()
        try:
            merged: list[np.ndarray] = []
            horizons: list[int] = []
            for w in work:
                h = int(w.request.forecast_horizon) if w.request.forecast_horizon else 16
                h = max(1, min(h, 512))
                horizons.append(h)
                for a in w.arrays:
                    merged.append(a)
            h_run = max(horizons) if horizons else 16
            h_run = max(1, min(int(h_run), 512))
            if not merged:
                err = ValueError("no_series_merged")
                for w in work:
                    if not w.done.done():
                        w.done.set_exception(err)
                return
            outs = await asyncio.to_thread(
                self._engine.predict_batch,
                merged,
                h_run,
            )
            if len(outs) != len(merged):
                err = RuntimeError("engine_batch_split_mismatch")
                for w in work:
                    if not w.done.done():
                        w.done.set_exception(err)
                return
            off = 0
            for w in work:
                n = len(w.arrays)
                h_req = int(w.request.forecast_horizon) if w.request.forecast_horizon else 16
                h_req = max(1, min(int(h_req), 512))
                part = outs[off : off + n]
                off += n
                forecasts: list[pb2.ForecastTensor] = []
                for ts, fc in zip(w.request.series, part, strict=True):
                    f32 = np.asarray(fc, dtype=np.float32).reshape(-1)
                    f32 = f32[:h_req] if f32.size > h_req else f32
                    forecasts.append(
                        pb2.ForecastTensor(
                            asset_id=ts.asset_id,
                            forecast_f32_le=f32.tobytes(),
                            horizon=int(f32.size),
                        )
                    )
                mid = w.request.model_id or self._settings.timesfm_model_id
                self._set_trailing(w.context)
                w.done.set_result(
                    pb2.PredictBatchResponse(
                        forecasts=forecasts,
                        backend=self._engine.backend_name,
                        model_id=mid[:200],
                    )
                )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            schedule_batch_metric_report(
                self._settings,
                batch_size=len(merged),
                forecast_horizon=h_run,
                latency_ms=latency_ms,
                backend=self._engine.backend_name,
            )
        except Exception as exc:  # noqa: BLE001
            for w in work:
                if not w.done.done():
                    w.done.set_exception(exc)
        finally:
            self._sem.release()

    async def _predict_batch_direct(
        self,
        request: pb2.PredictBatchRequest,
        context: grpc.aio.ServicerContext,
    ) -> pb2.PredictBatchResponse:
        t0 = time.perf_counter()
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
            self._set_trailing(context)
            return pb2.PredictBatchResponse(
                forecasts=forecasts,
                backend=self._engine.backend_name,
                model_id=mid[:200],
            )
        finally:
            self._sem.release()

    async def PredictBatch(self, request: pb2.PredictBatchRequest, context: grpc.aio.ServicerContext) -> pb2.PredictBatchResponse:  # type: ignore[name-defined]
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
        if self._batcher is not None and len(request.series) > 0:
            return await self._batcher.submit(request=request, context=context, arrays=arrays)
        return await self._predict_batch_direct(request, context)

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
