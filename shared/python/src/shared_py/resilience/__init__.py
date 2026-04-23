"""Resilience: Circuit-Breaker, Backoff und Survival-Mode (Regime-Disruption)."""

from __future__ import annotations

import threading
import time
from typing import Any

from shared_py.resilience.survival_kernel import (
    SYSTEM_ENTER_SURVIVAL_MODE,
    SYSTEM_EXIT_SURVIVAL_MODE,
    SurvivalKernelParams,
    SurvivalMetrics,
    SurvivalTickResult,
    apply_survival_signal_overrides,
    build_safety_incident_diagnosis_survival,
    merge_survival_truth,
    process_survival_metrics,
    publish_survival_hedge_operator_intel,
    publish_survival_system_events,
    read_survival_state_from_redis,
    survival_tick,
    write_survival_state_to_redis,
)


def compute_backoff_delay(attempt: int, *, base_sec: float, max_sec: float) -> float:
    return min(max_sec, base_sec * (2**attempt))


def is_retryable_http_status(status: int | None) -> bool:
    if status is None:
        return False
    if status == 429:
        return True
    return 500 <= status <= 599


class CircuitBreaker:
    """Einfacher Circuit Breaker pro Ressource."""

    def __init__(self, *, fail_threshold: int, open_seconds: int) -> None:
        self._fail_threshold = max(1, fail_threshold)
        self._open_seconds = max(1, open_seconds)
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_open(self, key: str) -> bool:
        with self._lock:
            until = self._open_until.get(key)
            if until is None:
                return False
            if time.monotonic() < until:
                return True
            self._open_until.pop(key, None)
            self._failures[key] = 0
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures[key] = 0
            self._open_until.pop(key, None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            failures = self._failures.get(key, 0) + 1
            self._failures[key] = failures
            if failures >= self._fail_threshold:
                self._open_until[key] = time.monotonic() + self._open_seconds
                self._failures[key] = 0

    def state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "failures": dict(self._failures),
                "open_until_mono": dict(self._open_until),
            }


__all__ = [
    "SYSTEM_ENTER_SURVIVAL_MODE",
    "SYSTEM_EXIT_SURVIVAL_MODE",
    "CircuitBreaker",
    "SurvivalKernelParams",
    "SurvivalMetrics",
    "SurvivalTickResult",
    "apply_survival_signal_overrides",
    "build_safety_incident_diagnosis_survival",
    "compute_backoff_delay",
    "is_retryable_http_status",
    "merge_survival_truth",
    "process_survival_metrics",
    "publish_survival_hedge_operator_intel",
    "publish_survival_system_events",
    "read_survival_state_from_redis",
    "survival_tick",
    "write_survival_state_to_redis",
]
