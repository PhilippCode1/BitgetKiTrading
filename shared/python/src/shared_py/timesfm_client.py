"""
Asynchroner gRPC-Client fuer den Apex ``TimesFmInference``-Dienst (TimesFM / Stub-Backend).

- Fester Call-Deadline (default 5s), manuelle Retries mit exponentiellem Backoff auf UNAVAILABLE.
- Fail-Closed: :class:`InferenceUnavailableError` bei Nicht-Erreichbarkeit / DEADLINE_EXCEEDED.

Benötigt ``grpcio`` (z. B. ``pip install "shared-py[grpc]"`` aus ``shared/python``).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import numpy as np

from shared_py.resilience import CircuitBreaker

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
    _FATAL_INFERENCE_CODES: frozenset[Any] = frozenset(
        {
            _grpc.StatusCode.UNAVAILABLE,
            _grpc.StatusCode.DEADLINE_EXCEEDED,
            _grpc.StatusCode.RESOURCE_EXHAUSTED,
        }
    )
else:
    _CB_FAIL_CODES = frozenset()
    _FATAL_INFERENCE_CODES = frozenset()

DEFAULT_INFERENCE_DEADLINE_SEC = 5.0
# P77: muss mit inference_server.inference_telemetry uebereinstimmen
_GRPC_MD_INFERENCE_SATURATION = "x-inference-saturation"
_SHADOW_BACKOFF_SEC = 2.0


def _trailing_metadata_saturated(md: Any) -> bool:
    if md is None:
        return False
    try:
        it = list(md)
    except Exception:  # noqa: BLE001
        return False
    for pair in it:
        if not pair or len(pair) < 2:
            continue
        k, v = pair[0], pair[1]
        ks = k if isinstance(k, str) else k.decode("utf-8", errors="ignore")
        if isinstance(v, bytes | bytearray):
            vs = v.decode("utf-8", errors="ignore")
        else:
            vs = str(v)
        if ks.lower() == _GRPC_MD_INFERENCE_SATURATION and vs.strip().lower() == "high":
            return True
    return False
_INFERENCE_SERVICE_CONFIG = json.dumps(
    {
        "methodConfig": [
            {
                "name": [{"service": "apex.timesfm.v1.TimesFmInference"}],
                "retryPolicy": {
                    "maxAttempts": 4,
                    "initialBackoff": "0.1s",
                    "maxBackoff": "0.4s",
                    "backoffMultiplier": 2,
                    "retryableStatusCodes": ["UNAVAILABLE"],
                },
            }
        ],
    }
)


class InferenceUnavailableError(Exception):
    """Apex/TSFM: Inferenz steht nicht zuverlaessig zur Verfuegung (Timeout, gRPC, Ueberlast)."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


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
    gRPC-aio Client: Circuit Breaker, Deadline, Retries (UNAVAILABLE), Fail-Closed Exception.
    """

    def __init__(
        self,
        target: str,
        *,
        circuit_breaker: CircuitBreaker | None = None,
        circuit_key: str = "timesfm_grpc",
        deadline_sec: float = DEFAULT_INFERENCE_DEADLINE_SEC,
        max_unavailable_retries: int = 3,
        chaos_inject_every_n: int = 0,
        chaos_inject_delay_sec: float = 6.0,
    ) -> None:
        if _grpc is None:
            raise ImportError(
                "grpcio fehlt — bitte installieren (z. B. pip install grpcio)."
            ) from _GRPC_IMPORT_ERROR
        self._target = (target or "").strip()
        self._grpc_aio = __import__("grpc.aio", fromlist=["aio"])
        self._channel: Any = None
        self._stub: Any = None
        self._cb = circuit_breaker or CircuitBreaker(fail_threshold=4, open_seconds=45)
        self._circuit_key = circuit_key
        self._deadline_sec = float(
            min(max(0.5, deadline_sec), 30.0),
        )
        self._max_unavailable_retries = int(max(0, max_unavailable_retries))
        self._chaos_n = int(max(0, chaos_inject_every_n))
        self._chaos_delay = float(max(0.0, chaos_inject_delay_sec))
        self._shadow_backoff_until = 0.0

    async def __aenter__(self) -> TimesFmGrpcClient:
        _, pb2_grpc = _load_pb()
        options = [
            ("grpc.service_config", _INFERENCE_SERVICE_CONFIG),
            ("grpc.keepalive_time_ms", 20_000),
        ]
        interceptors: list[Any] = []
        if self._chaos_n > 0 and self._chaos_delay > 0:
            from shared_py.chaos.grpc_chaos import build_timesfm_chaos_interceptors

            interceptors = build_timesfm_chaos_interceptors(
                every_n=self._chaos_n,
                delay_sec=self._chaos_delay,
            )
        ch_kw: dict[str, Any] = {"options": options}
        if interceptors:
            ch_kw["interceptors"] = interceptors
        self._channel = self._grpc_aio.insecure_channel(self._target, **ch_kw)
        self._stub = pb2_grpc.TimesFmInferenceStub(self._channel)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._channel is not None:
            await self._channel.close()
        self._channel = None
        self._stub = None

    def _backoff_s(self, attempt: int) -> float:
        return min(0.8, 0.05 * (2.0**float(attempt)))

    def _unavailableish(self, exc: Any) -> bool:
        try:
            return _grpc is not None and bool(exc) and exc.code() == _grpc.StatusCode.UNAVAILABLE
        except Exception:  # noqa: BLE001
            return False

    async def predict_batch(
        self,
        series: Sequence[tuple[str, np.ndarray]],
        *,
        forecast_horizon: int = 16,
        model_id: str = "",
        timeout_sec: float = DEFAULT_INFERENCE_DEADLINE_SEC,
        inference_priority: str = "live",
    ) -> list[np.ndarray]:
        if self._stub is None:
            raise RuntimeError("TimesFmGrpcClient: vorher async with / connect verwenden")
        if self._cb.is_open(self._circuit_key):
            raise InferenceUnavailableError("timesfm_grpc_circuit_open", code="circuit_open")
        prio = (inference_priority or "live").strip().lower()
        if prio == "shadow":
            now = time.monotonic()
            if now < self._shadow_backoff_until:
                await asyncio.sleep(self._shadow_backoff_until - now)
        pb2, _pb2_grpc = _load_pb()
        req = pb2.PredictBatchRequest(
            series=[_encode_series(pb2, aid, arr) for aid, arr in series],
            forecast_horizon=int(forecast_horizon),
            model_id=model_id or "",
        )
        tdead = float(min(max(0.5, timeout_sec), 30.0))
        last_exc: BaseException | None = None
        for attempt in range(self._max_unavailable_retries + 1):
            if attempt:
                await asyncio.sleep(self._backoff_s(attempt - 1))
            try:
                call = self._stub.PredictBatch(req, timeout=tdead)
                resp = await call
                try:
                    tm = await call.trailing_metadata()
                except Exception:  # noqa: BLE001
                    tm = None
                if prio == "shadow" and _trailing_metadata_saturated(tm):
                    self._shadow_backoff_until = time.monotonic() + _SHADOW_BACKOFF_SEC
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
            except self._grpc_aio.AioRpcError as exc:
                last_exc = exc
                if exc.code() in _CB_FAIL_CODES:
                    self._cb.record_failure(self._circuit_key)
                if self._unavailableish(exc) and attempt < self._max_unavailable_retries:
                    continue
                c = str(exc.code()) if exc and hasattr(exc, "code") else "unknown"
                det = str(exc.details() or "")[:500]
                if _grpc is not None and _fatal_inference_codes_hits(exc.code()):
                    raise InferenceUnavailableError(
                        f"TimesFM/PredictBatch nicht verfuegbar ({c}): {det}",
                        code=c,
                    ) from exc
                raise
        assert last_exc is not None
        c = str(last_exc.code()) if last_exc and hasattr(last_exc, "code") else "unknown"
        raise InferenceUnavailableError(
            f"TimesFM/PredictBatch: retries erschoepft ({c})",
            code=c,
        ) from last_exc

    async def stream_ticks(
        self,
        tick_source: AsyncIterator[Any],
        *,
        timeout_sec: float | None = None,
    ) -> AsyncIterator[Any]:
        if self._stub is None:
            raise RuntimeError("TimesFmGrpcClient: vorher async with / connect verwenden")
        t = self._deadline_sec if timeout_sec is None else float(min(max(0.5, timeout_sec), 60.0))
        if self._cb.is_open(self._circuit_key):
            raise InferenceUnavailableError("timesfm_grpc_circuit_open", code="circuit_open")
        call = self._stub.StreamTicks(tick_source, timeout=t)
        try:
            async for frame in call:
                yield frame
        except self._grpc_aio.AioRpcError as exc:
            if exc.code() in _CB_FAIL_CODES:
                self._cb.record_failure(self._circuit_key)
            if _grpc is not None and exc.code() in _FATAL_INFERENCE_CODES:
                raise InferenceUnavailableError(
                    f"TimesFM/StreamTicks fehlgeschlagen: {exc.code()}: "
                    f"{(str(exc.details() or '')[:200])}",
                    code=str(exc.code()) if exc and hasattr(exc, "code") else None,
                ) from exc
            raise
        else:
            self._cb.record_success(self._circuit_key)


def _fatal_inference_codes_hits(c: Any) -> bool:
    if _grpc is None:
        return True
    try:
        return c in _FATAL_INFERENCE_CODES
    except Exception:  # noqa: BLE001
        return True


async def predict_batch_numpy(
    target: str,
    series: Sequence[tuple[str, np.ndarray]],
    *,
    forecast_horizon: int = 16,
    model_id: str = "",
    timeout_sec: float = DEFAULT_INFERENCE_DEADLINE_SEC,
    inference_priority: str = "live",
) -> list[np.ndarray]:
    """Kurzform: ein Kanal pro Aufruf (fuer Skripte/Tests)."""
    async with TimesFmGrpcClient(target) as client:
        return await client.predict_batch(
            series,
            forecast_horizon=forecast_horizon,
            model_id=model_id,
            timeout_sec=timeout_sec,
            inference_priority=inference_priority,
        )


def predict_batch_numpy_sync(
    target: str,
    series: Sequence[tuple[str, np.ndarray]],
    *,
    forecast_horizon: int = 16,
    model_id: str = "",
    timeout_sec: float = DEFAULT_INFERENCE_DEADLINE_SEC,
    inference_priority: str = "live",
) -> list[np.ndarray]:
    """Synchroner Wrapper fuer einfache CLI-/Testskripte."""
    return asyncio.run(
        predict_batch_numpy(
            target,
            series,
            forecast_horizon=forecast_horizon,
            model_id=model_id,
            timeout_sec=timeout_sec,
            inference_priority=inference_priority,
        )
    )
