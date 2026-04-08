from __future__ import annotations

import time


class PublishDedupe:
    """In-Memory Rate-Limit fuer events:system_alert (pro alert_key)."""

    def __init__(self) -> None:
        self._last_publish_ts: dict[str, float] = {}

    def allow_publish(self, alert_key: str, dedupe_sec: int) -> bool:
        now = time.time()
        last = self._last_publish_ts.get(alert_key, 0.0)
        if now - last < float(dedupe_sec):
            return False
        self._last_publish_ts[alert_key] = now
        return True
