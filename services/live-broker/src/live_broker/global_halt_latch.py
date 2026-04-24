"""
In-Process-Sicherheits-Latch fuer ``system:global_halt`` (Redis).

- Laufwerk: Pub/Sub auf :data:`PUB_CHANNEL` + initialer ``GET`` des Keys.
- Aktivieren (Ops/Tests): :func:`publish_global_halt_state` (SET + PUBLISH) oder
  manuell Key setzen und passende Publish-Nachricht senden.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import redis

from live_broker.exceptions import GlobalHaltException

logger = logging.getLogger("live_broker.global_halt")

# Redis-Key (string): "1"/"true" = Halt, "0"/"false"/leer = frei
REDIS_KEY_GLOBAL_HALT = "system:global_halt"
# Gleicher Kanal-Name: Broker-Instanzen subscriben hier
PUB_CHANNEL = "system:global_halt:pub"


def _parse_halt_value(raw: str | None) -> bool:
    if raw is None:
        return False
    s = str(raw).strip().lower()
    if s in ("", "0", "false", "no", "off", "ok", "release", "go"):
        return False
    return s in (
        "1",
        "true",
        "yes",
        "on",
        "halt",
        "stop",
        "global_halt",
        "emergency",
    ) or s.startswith("halt")  # "halt:reason"


class GlobalHaltLatch:
    """In-Memory-Flag; Updates via Pub/Sub (kein DSN-Read im Submit-Hotpath)."""

    def __init__(self, redis_url: str) -> None:
        self._url = (redis_url or "").strip()
        self._lock = threading.Lock()
        self._halted = False
        self._thread: threading.Thread | None = None
        self._sub_r: Any = None
        self._main_r: Any = None
        self._running = False

    @property
    def is_halted(self) -> bool:
        with self._lock:
            return self._halted

    def _set_halted(self, value: bool) -> None:
        with self._lock:
            if self._halted == value:
                return
            self._halted = value
            if value:
                logger.critical(
                    "GLOBAL_HALT: In-Process-Latch = True (keine Order-Mutationen)"
                )

    def _apply_from_raw(self, raw: str | None) -> None:
        self._set_halted(_parse_halt_value(raw))

    def _pubsub_loop(self) -> None:
        assert self._sub_r is not None
        pubsub = self._sub_r.pubsub(ignore_subscribe_messages=False)
        try:
            pubsub.subscribe(PUB_CHANNEL)
            for msg in pubsub.listen():
                if not self._running:
                    break
                if not isinstance(msg, dict):
                    continue
                mtype = msg.get("type")
                if mtype == "message":
                    data = msg.get("data")
                    if isinstance(data, bytes):
                        raw: str | None = data.decode()
                    elif data is None:
                        raw = None
                    else:
                        raw = str(data)
                    self._apply_from_raw(raw)
        except Exception as exc:  # noqa: BLE001
            if self._running:
                logger.exception("global_halt pubsub beendet: %s", exc)
        finally:
            try:
                pubsub.close()
            except Exception:  # noqa: BLE001
                pass

    def start(self) -> None:
        if not self._url:
            logger.warning("GLOBAL_HALT: kein REDIS_URL — Latch inaktiv")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        try:
            self._main_r = redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=30.0,
            )
            self._sub_r = redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=30.0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("GLOBAL_HALT: Redis-Client fehlgeschlagen: %s", exc)
            return
        try:
            v = self._main_r.get(REDIS_KEY_GLOBAL_HALT)
            self._apply_from_raw(v)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GLOBAL_HALT: initialer GET fehlgeschlagen: %s", exc)
        self._running = True
        self._thread = threading.Thread(
            target=self._pubsub_loop,
            name="live-broker-global-halt-pubsub",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "GLOBAL_HALT: Pub/Sub-Thread gestartet (key=%s)", REDIS_KEY_GLOBAL_HALT
        )

    def stop(self) -> None:
        self._running = False
        if self._sub_r is not None:
            try:
                self._sub_r.close()
            except Exception:  # noqa: BLE001
                pass
        self._thread = None
        self._sub_r = None
        self._main_r = None

    def assert_not_halted(self) -> None:
        """Nur In-Memory (Pub/Sub haelt den Zustand aktuell)."""
        if self.is_halted:
            raise GlobalHaltException(
                "Global Halt (Redis) — Order-Mutationen bis Aufhebung gesperrt"
            )

    def force_halt_in_process(self, *, reason: str = "infrastructure_redis_loss") -> None:
        """
        Fail-Closed, wenn ``SET system:global_halt`` wegen ausgefallenem Redis nicht
        sofort spiegelbar ist (Prompt 72) — lokal keine Order-Mutationen mehr.
        """
        self._set_halted(True)
        logger.critical("GLOBAL_HALT: force in-process (reason=%s)", reason)


def publish_global_halt_state(redis_url: str, active: bool) -> None:
    """
    Zentraler Schalter: SET + PUBLISH, damit alle Broker-Prozesse den Latch
    ohne Postgres aktualisieren.
    """
    u = (redis_url or "").strip()
    if not u:
        raise ValueError("redis_url fehlt")
    r = redis.Redis.from_url(u, decode_responses=True, socket_connect_timeout=2)
    payload = "1" if active else "0"
    r.set(REDIS_KEY_GLOBAL_HALT, payload)
    r.publish(PUB_CHANNEL, payload)


def try_publish_global_halt_state(redis_url: str, active: bool) -> bool:
    """
    Wie :func:`publish_global_halt_state`, aber ``False`` bei
    Verbindungs-/Redis-Fehler (z. B. während Container-Stop).
    """
    u = (redis_url or "").strip()
    if not u:
        return False
    try:
        publish_global_halt_state(u, active)
    except (OSError, redis.exceptions.RedisError, ValueError):
        return False
    return True
