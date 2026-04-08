from __future__ import annotations

import logging

import psycopg

logger = logging.getLogger("alert_engine.repo_state")


class RepoBotState:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def get_last_update_id(self) -> int:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT last_update_id FROM alert.bot_state WHERE key = 'telegram'"
            ).fetchone()
            if row is None:
                return 0
            return int(row[0])

    def set_last_update_id(self, uid: int) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.bot_state (key, last_update_id, updated_ts)
                VALUES ('telegram', %s, now())
                ON CONFLICT (key) DO UPDATE SET
                  last_update_id = EXCLUDED.last_update_id,
                  updated_ts = now()
                """,
                (uid,),
            )
            conn.commit()
        logger.debug("persisted telegram last_update_id=%s", uid)
