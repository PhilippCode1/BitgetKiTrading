"""
Bewertet Live-MSE mit ADWIN + Konfidenz, publiziert ``drift_event``,
startet Drift-Retrain (nur Challenger).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from shared_py.eventbus import STREAM_DRIFT_EVENT, RedisStreamBus
from shared_py.eventbus.envelope import EventEnvelope

from learning_engine.drift.adwin_detector import MseAdwinDriftMonitor, MseDriftStep
from learning_engine.drift.drift_retrain_subprocess import run_drift_retrain
from learning_engine.storage.connection import db_connect

if TYPE_CHECKING:
    from learning_engine.config import LearningEngineSettings

log = logging.getLogger("learning_engine.drift_action")


def _ts_ms() -> int:
    return int(time.time() * 1000)


class DriftActionCoordinator:
    """
    ``on_mse`` mit MSE-Stream fuettern. Bei Drift+Konfidenz: Event, Log
    ``AUTO_RETRAIN_TRIGGERED``, In-Process-Retrain oder Subprozess.
    """

    def __init__(
        self,
        settings: LearningEngineSettings,
        *,
        monitor: MseAdwinDriftMonitor | None = None,
        retrain_handler: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._retrain_handler = retrain_handler
        self._monitor = monitor or MseAdwinDriftMonitor(
            min_confidence=settings.learning_drift_mse_min_confidence
        )
        self._last_trigger_mono: float = 0.0
        self._bus: RedisStreamBus | None = None
        # Nach einem Trigger: frisches Fenster, damit anhaltender Regimewechsel
        # nicht pro weiterem MSE-Tick erneut feuert (Kooldown + ein Episoden-Reset).
        self._monitor_ctor = self._default_monitor_from_current

    def _default_monitor_from_current(self) -> MseAdwinDriftMonitor:
        m = self._monitor
        return MseAdwinDriftMonitor(
            delta=m.adwin.delta,
            min_window=m.adwin.min_window,
            max_window=m.adwin.max_window,
            min_confidence=m.min_confidence,
        )

    def on_mse(self, mse: float) -> MseDriftStep | None:
        step = self._monitor.update(mse)
        if step is None or not step.drift:
            return step
        cool = int(self._settings.learning_drift_retrain_cooldown_sec)
        if cool > 0 and (time.monotonic() - self._last_trigger_mono) < float(cool):
            return step
        self._last_trigger_mono = time.monotonic()
        log.warning(
            "AUTO_RETRAIN_TRIGGERED mse=%.6g p_value=%.6g "
            "confidence=%.6g adwin_index=%d",
            float(mse),
            step.p_value,
            step.confidence,
            int(step.index),
        )
        if not self._settings.learning_drift_skip_event_bus:
            self._publish_drift(mse, step)
        if self._retrain_handler is not None:
            self._retrain_handler()
        elif self._settings.learning_drift_retrain_inprocess:
            self._retrain_inprocess()
        else:
            self._spawn_retrain_subprocess()
        self._monitor = self._monitor_ctor()
        return step

    def _get_bus(self) -> RedisStreamBus:
        if self._bus is None:
            self._bus = RedisStreamBus.from_url(
                self._settings.redis_url,
                default_block_ms=self._settings.eventbus_block_ms,
                default_count=self._settings.eventbus_count,
            )
        return self._bus

    def _publish_drift(self, mse: float, step: MseDriftStep) -> None:
        bus = self._get_bus()
        env = EventEnvelope(
            event_type="drift_event",
            exchange_ts_ms=_ts_ms(),
            payload={
                "drift_class": "mse_adwin",
                "model_name": self._settings.model_champion_name,
                "confidence": float(step.confidence),
                "mse_current": float(mse),
                "adwin_index": int(step.index),
            },
        )
        env.validate_payload()
        bus.publish(STREAM_DRIFT_EVENT, env)

    def _retrain_inprocess(self) -> None:
        with db_connect(self._settings.database_url) as conn:
            with conn.transaction():
                run_drift_retrain(conn, self._settings)

    def _spawn_retrain_subprocess(self) -> None:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        w = int(self._settings.learning_drift_retrain_window_days)
        env["LEARNING_DRIFT_RETRAIN_WINDOW_DAYS"] = str(w)
        if self._settings.learning_drift_retrain_smoke:
            env["LEARNING_DRIFT_RETRAIN_SMOKE"] = "1"
        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "learning_engine.drift.drift_retrain_subprocess",
                ],
                env=env,
                close_fds=False if sys.platform == "win32" else True,
                start_new_session=sys.platform != "win32",
            )
        except OSError as e:
            log.error("retrain subprozess fehlgeschlagen: %s", e, exc_info=True)
