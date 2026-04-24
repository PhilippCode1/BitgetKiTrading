"""
P77: GPU-/Warteschlangen-Telemetrie fuer /metrics (Prometheus) + Saettigungs-Kennzahlen
fuer gRPC-Trailing-Metadata.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Final

from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

logger = logging.getLogger("inference_server.telemetry")

_pynvml: Any = None
_NVML_OK: bool = False
_nvml_lock: threading.RLock = threading.RLock()
_nvml_inited: bool = False
_last_gpu: dict[str, float] = {
    "vram_used": 0.0,
    "vram_total": 0.0,
    "util": 0.0,
}
_last_gpu_error: str | None = None

G_GPU_VRAM_USED: Final = Gauge(
    "gpu_vram_used_bytes",
    "NVIDIA: belegter VRAM (Device 0)",
    labelnames=["gpu_index"],
)
G_GPU_VRAM_TOTAL: Final = Gauge(
    "gpu_vram_total_bytes",
    "NVIDIA: Gesamt-VRAM (Device 0)",
    labelnames=["gpu_index"],
)
G_GPU_UTIL: Final = Gauge(
    "gpu_utilization_percent",
    "NVIDIA: GPU-Last (Device 0, 0-100 aus nvmlUtilization.gpu)",
    labelnames=["gpu_index"],
)
G_QUEUE_DEPTH: Final = Gauge(
    "inference_queue_depth",
    "Wartende PredictBatch-Arbeiten im Dynamic-Batch-Puffer (0 wenn Batching aus)",
    [],
)
_queue_depth_getter: Callable[[], int] | None = None

G_GPU_VRAM_USED.labels("0").set(0)
G_GPU_VRAM_TOTAL.labels("0").set(0)
G_GPU_UTIL.labels("0").set(0)
G_QUEUE_DEPTH.set(0)

try:  # pragma: no cover
    import pynvml as _pynvml  # type: ignore[import-untyped, import-not-found]
except ImportError:
    _pynvml = None  # type: ignore[misc, assignment]

_GRPC_MD_SATURATION: Final = "x-inference-saturation"
_GRPC_MD_VRAM_FREE_MIB: Final = "x-inference-vram-free-mib"
_UTIL_PCT: Final = 90.0  # gleichbedeutend mit >90% in Prometheus-Alert
_VRAM_MIN_FREE_BYTES: Final = 512 * 1024 * 1024


def set_queue_depth_getter(fn: Callable[[], int] | None) -> None:
    global _queue_depth_getter
    _queue_depth_getter = fn


def _try_nvml_init() -> bool:
    global _NVML_OK, _nvml_inited, _pynvml, _last_gpu_error
    if _pynvml is None or _nvml_inited:
        return _NVML_OK
    with _nvml_lock:
        if _nvml_inited:
            return _NVML_OK
        try:
            _pynvml.nvmlInit()
            _nvml_inited = True
            _NVML_OK = True
            _last_gpu_error = None
        except Exception as exc:  # noqa: BLE001
            _last_gpu_error = str(exc)[:200]
            logger.info("pynvml: GPU-Metriken deaktiviert: %s", _last_gpu_error)
            _NVML_OK = False
            _nvml_inited = True
        return _NVML_OK


def _refresh_gpu_gauges_sync() -> None:
    global _last_gpu, _pynvml, _last_gpu_error
    if not _try_nvml_init() or _pynvml is None:
        G_GPU_VRAM_USED.labels("0").set(0)
        G_GPU_VRAM_TOTAL.labels("0").set(0)
        G_GPU_UTIL.labels("0").set(0)
        with _nvml_lock:
            _last_gpu = {"vram_used": 0.0, "vram_total": 0.0, "util": 0.0}
        return
    try:
        h = _pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = _pynvml.nvmlDeviceGetMemoryInfo(h)
        u = _pynvml.nvmlDeviceGetUtilizationRates(h)
        v_used = float(mem.used)
        v_total = float(mem.total)
        util = float(getattr(u, "gpu", 0) or 0)
    except Exception as exc:  # noqa: BLE001
        _last_gpu_error = str(exc)[:200]
        v_used, v_total, util = 0.0, 0.0, 0.0
    with _nvml_lock:
        _last_gpu = {"vram_used": v_used, "vram_total": v_total, "util": util}
    G_GPU_VRAM_USED.labels("0").set(v_used)
    G_GPU_VRAM_TOTAL.labels("0").set(v_total)
    G_GPU_UTIL.labels("0").set(util)


def _refresh_queue_gauge() -> None:
    fn = _queue_depth_getter
    d = 0
    if fn is not None:
        try:
            d = int(max(0, fn()))
        except Exception:  # noqa: BLE001
            d = 0
    G_QUEUE_DEPTH.set(d)


def refresh_all_metrics() -> None:
    """Eine Synchronrunde: GPU + Warteschlange; NVML blockierend im Call-Thread."""
    _refresh_gpu_gauges_sync()
    _refresh_queue_gauge()


def last_gpu_state() -> dict[str, float]:
    with _nvml_lock:
        return dict(_last_gpu)


def is_inference_saturated() -> bool:
    s = last_gpu_state()
    total = s.get("vram_total", 0.0)
    used = s.get("vram_used", 0.0)
    util_p = s.get("util", 0.0)
    v_free = max(0.0, total - used) if total > 0 else 0.0
    if util_p >= _UTIL_PCT:
        return True
    if total > 0 and v_free < _VRAM_MIN_FREE_BYTES:
        return True
    return False


def trailing_metadata_tuples() -> list[tuple[str, str]]:
    s = last_gpu_state()
    total = s.get("vram_total", 0.0)
    used = s.get("vram_used", 0.0)
    v_free = max(0.0, total - used) if total > 0 else 0.0
    v_free_mib = v_free / (1024.0 * 1024.0)
    sat = is_inference_saturated()
    return [
        (_GRPC_MD_SATURATION, "high" if sat else "ok"),
        (_GRPC_MD_VRAM_FREE_MIB, f"{v_free_mib:.1f}"),
    ]


def render_metrics() -> tuple[bytes, str]:
    return generate_latest() + b"\n", CONTENT_TYPE_LATEST
