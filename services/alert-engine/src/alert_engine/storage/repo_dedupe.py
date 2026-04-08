from __future__ import annotations

import logging
from datetime import timedelta

import psycopg

from alert_engine.log_safety import safe_key_ref

logger = logging.getLogger("alert_engine.repo_dedupe")


class RepoDedupe:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def try_acquire(self, dedupe_key: str, ttl_minutes: int) -> bool:
        """Return True if this is the first time (insert ok), False if duplicate."""
        with psycopg.connect(self._dsn) as conn:
            conn.execute("DELETE FROM alert.dedupe_keys WHERE expires_ts < now()")
            row = conn.execute(
                """
                INSERT INTO alert.dedupe_keys (dedupe_key, expires_ts)
                VALUES (%s, now() + %s)
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING dedupe_key
                """,
                (dedupe_key, timedelta(minutes=ttl_minutes)),
            ).fetchone()
            conn.commit()
        ok = row is not None
        if not ok:
            logger.info("dedupe skip %s", safe_key_ref(dedupe_key))
        return ok
