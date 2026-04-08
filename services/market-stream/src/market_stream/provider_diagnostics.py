from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderDiagnostics:
    """Thread-sichere Oberfläche für Bitget-Protokollfehler vs. Transport-Störungen."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    _protocol_ts_ms: int | None = field(default=None, repr=False)
    _protocol_source: str | None = field(default=None, repr=False)
    _protocol_detail: str | None = field(default=None, repr=False)
    _transport_ts_ms: int | None = field(default=None, repr=False)
    _transport_detail: str | None = field(default=None, repr=False)

    def record_protocol_error(self, source: str, detail: str, *, max_len: int = 2000) -> None:
        """Bitget/API-Protokoll: WS-error-Event, REST code != 00000, HTTP 4xx/5xx nach Body."""
        detail_s = (detail or "")[:max_len]
        now = int(time.time() * 1000)
        with self._lock:
            self._protocol_ts_ms = now
            self._protocol_source = source
            self._protocol_detail = detail_s

    def record_transport_error(self, detail: str, *, max_len: int = 2000) -> None:
        """Netzwerk/Timeout/Verbindungsabbruch — erwartbar bei kurzen Störungen."""
        detail_s = (detail or "")[:max_len]
        now = int(time.time() * 1000)
        with self._lock:
            self._transport_ts_ms = now
            self._transport_detail = detail_s

    def as_health_fragment(self) -> dict[str, Any]:
        with self._lock:
            proto: dict[str, Any] | None = None
            if self._protocol_ts_ms is not None:
                proto = {
                    "ts_ms": self._protocol_ts_ms,
                    "source": self._protocol_source,
                    "detail": self._protocol_detail,
                }
            trans: dict[str, Any] | None = None
            if self._transport_ts_ms is not None:
                trans = {
                    "ts_ms": self._transport_ts_ms,
                    "detail": self._transport_detail,
                }
            return {
                "protocol": proto,
                "transport": trans,
            }
