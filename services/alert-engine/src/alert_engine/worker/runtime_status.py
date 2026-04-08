from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class RuntimeStatus:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    redis_ok: bool = False
    db_ok: bool = False
    pending_outbox: int = 0

    def set_all(self, *, redis_ok: bool, db_ok: bool, pending: int) -> None:
        with self._lock:
            self.redis_ok = redis_ok
            self.db_ok = db_ok
            self.pending_outbox = pending

    def snapshot(self) -> tuple[bool, bool, int]:
        with self._lock:
            return self.redis_ok, self.db_ok, self.pending_outbox
