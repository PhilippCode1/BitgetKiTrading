from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("alert_engine.repo_subscriptions")


class RepoSubscriptions:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def ensure_allowed_from_env(self, chat_ids: set[int]) -> None:
        if not chat_ids:
            return
        with psycopg.connect(self._dsn) as conn:
            for cid in chat_ids:
                conn.execute(
                    """
                    INSERT INTO alert.chat_subscriptions (chat_id, status)
                    VALUES (%s, 'allowed')
                    ON CONFLICT (chat_id) DO UPDATE SET
                      status = CASE
                        WHEN alert.chat_subscriptions.status = 'blocked' THEN 'blocked'
                        ELSE 'allowed'
                      END
                    """,
                    (cid,),
                )
            conn.commit()
        logger.info("synced %s allowed chat ids from env", len(chat_ids))

    def upsert_start(
        self,
        chat_id: int,
        user_id: int | None,
        username: str | None,
        title: str | None,
        *,
        force_allowed: bool,
    ) -> str:
        desired = "allowed" if force_allowed else "pending"
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT status FROM alert.chat_subscriptions WHERE chat_id = %s", (chat_id,)
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO alert.chat_subscriptions (chat_id, status, user_id, username, title)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (chat_id, desired, user_id, username, title),
                )
            else:
                cur = str(row[0])
                new_status = cur
                if cur == "blocked":
                    new_status = "blocked"
                elif force_allowed or cur == "allowed":
                    new_status = "allowed"
                else:
                    new_status = "pending"
                conn.execute(
                    """
                    UPDATE alert.chat_subscriptions
                    SET status = %s,
                        user_id = COALESCE(%s, user_id),
                        username = COALESCE(%s, username),
                        title = COALESCE(%s, title)
                    WHERE chat_id = %s
                    """,
                    (new_status, user_id, username, title, chat_id),
                )
            row2 = conn.execute(
                "SELECT status FROM alert.chat_subscriptions WHERE chat_id = %s", (chat_id,)
            ).fetchone()
            conn.commit()
        return str(row2[0]) if row2 else desired

    def get_status(self, chat_id: int) -> str | None:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT status FROM alert.chat_subscriptions WHERE chat_id = %s", (chat_id,)
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def set_status(self, chat_id: int, status: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            cur = conn.execute(
                "UPDATE alert.chat_subscriptions SET status = %s WHERE chat_id = %s",
                (status, chat_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def upsert_chat_status(self, chat_id: int, status: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.chat_subscriptions (chat_id, status)
                VALUES (%s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET status = EXCLUDED.status
                """,
                (chat_id, status),
            )
            conn.commit()

    def list_allowed_chat_ids(self) -> list[int]:
        now_ms = int(time.time() * 1000)
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT chat_id FROM alert.chat_subscriptions
                WHERE status = 'allowed'
                  AND (muted_until_ts_ms IS NULL OR muted_until_ts_ms < %s)
                """,
                (now_ms,),
            ).fetchall()
        return [int(r["chat_id"]) for r in rows]

    def is_chat_allowed(self, chat_id: int) -> bool:
        return chat_id in self.list_allowed_chat_ids()

    def set_mute(self, chat_id: int, until_ms: int | None) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                "UPDATE alert.chat_subscriptions SET muted_until_ts_ms = %s WHERE chat_id = %s",
                (until_ms, chat_id),
            )
            conn.commit()

    def get_muted_until(self, chat_id: int) -> int | None:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT muted_until_ts_ms FROM alert.chat_subscriptions WHERE chat_id = %s",
                (chat_id,),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])
