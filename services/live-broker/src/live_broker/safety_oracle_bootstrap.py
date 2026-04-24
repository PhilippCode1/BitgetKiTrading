from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal
from typing import Any

import psycopg
from shared_py.bitget.runtime_safety_oracle import (
    RuntimeSafetyConfig,
    RuntimeSafetyOracle,
)

from live_broker.config import LiveBrokerSettings
from live_broker.events import publish_operator_intel, publish_system_alert
from live_broker.global_halt_latch import try_publish_global_halt_state

logger = logging.getLogger("live_broker.safety_oracle")


def _default_symbol(settings: LiveBrokerSettings) -> str:
    s = (getattr(settings, "symbol", None) or "BTCUSDT-UMCBL").strip()
    return s[:64] if s else "SAFETY"


def _halt_fn(runtime: Any) -> None:
    def _inner(b: bool) -> None:
        s = (runtime.settings.redis_url or "").strip()
        if not s:
            runtime.global_halt.force_halt_in_process(
                reason="runtime_safety_oracle_no_redis"
            )
            return
        if not try_publish_global_halt_state(s, b):
            runtime.global_halt.force_halt_in_process(
                reason="runtime_safety_oracle_redis_set_failed"
            )

    return _inner


def _oracle_thread_body(stop_event: threading.Event, runtime: Any) -> None:
    settings: LiveBrokerSettings = runtime.settings
    dsn = (settings.database_url or "").strip()
    if not dsn:
        return
    cfg = RuntimeSafetyConfig(
        notional_to_equity_max=Decimal(
            str(settings.runtime_safety_max_notional_equity_mult or "10")
        ),
    )
    oracle = RuntimeSafetyOracle(config=cfg)
    sym = _default_symbol(settings)
    halt = _halt_fn(runtime)

    while not stop_event.is_set():
        t0 = time.perf_counter()
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                violations = oracle.evaluate_invariants(conn, equity_override=None)
                if violations:
                    oracle.maybe_emit_side_effects(
                        violations,
                        now=time.time(),
                        redis_url=settings.redis_url,
                        publish_halt=halt,
                        force_latch=lambda r: runtime.global_halt.force_halt_in_process(
                            reason=str(r)
                        ),
                        publish_system_alert=publish_system_alert,
                        publish_operator_intel=publish_operator_intel,
                        bus=runtime.bus,
                        symbol=sym,
                    )
        except (OSError, ValueError) as exc:
            logger.error("safety-oracle connect failed: %s", exc)
        except Exception:  # noqa: BLE001
            logger.exception("safety-oracle tick failed")
        wait = max(
            0.0,
            float(settings.runtime_safety_oracle_interval_sec)
            - (time.perf_counter() - t0),
        )
        if stop_event.wait(timeout=wait):
            break
    logger.info("runtime-safety-oracle thread stopped")


def start_runtime_safety_oracle_thread(runtime: Any) -> None:
    if not runtime.settings.runtime_safety_oracle_enabled:
        return
    t = getattr(runtime, "_safety_oracle_thread", None)
    if t is not None and t.is_alive():
        return
    dsn = (runtime.settings.database_url or "").strip()
    if not dsn:
        logger.warning("safety-oracle: kein database_url, Thread nicht gestartet")
        return
    th = threading.Thread(
        target=_oracle_thread_body,
        args=(runtime._stop, runtime),
        name="runtime-safety-oracle",
        daemon=True,
    )
    runtime._safety_oracle_thread = th
    th.start()
    logger.info(
        "runtime-safety-oracle thread started interval_sec=%s",
        runtime.settings.runtime_safety_oracle_interval_sec,
    )


def join_runtime_safety_oracle_thread(runtime: Any) -> None:
    t = getattr(runtime, "_safety_oracle_thread", None)
    if t is not None and t.is_alive():
        t.join(timeout=2.0)
    if hasattr(runtime, "_safety_oracle_thread"):
        runtime._safety_oracle_thread = None
