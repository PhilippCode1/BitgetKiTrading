from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("alert_engine.repo_outbox")


class RepoOutbox:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def insert_pending(
        self,
        *,
        alert_type: str,
        severity: str,
        symbol: str | None,
        timeframe: str | None,
        dedupe_key: str | None,
        chat_id: int,
        payload: dict[str, Any],
    ) -> str:
        aid = str(uuid.uuid4())
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.alert_outbox (
                  alert_id, alert_type, severity, symbol, timeframe, dedupe_key,
                  payload, chat_id, state
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')
                """,
                (
                    aid,
                    alert_type,
                    severity,
                    symbol,
                    timeframe,
                    dedupe_key,
                    json.dumps(payload),
                    chat_id,
                ),
            )
            conn.commit()
        logger.info("outbox inserted alert_id=%s type=%s chat_id=%s", aid, alert_type, chat_id)
        return aid

    def count_pending(self) -> int:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT count(*)::int AS c FROM alert.alert_outbox WHERE state = 'pending'"
            ).fetchone()
        return int(row[0]) if row else 0

    def count_state(self, state: str) -> int:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT count(*)::int AS c
                FROM alert.alert_outbox
                WHERE state = %s
                """,
                (state,),
            ).fetchone()
        return int(row[0]) if row else 0

    def oldest_pending_age_ms(self) -> int | None:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT extract(epoch FROM (now() - min(created_ts))) * 1000
                FROM alert.alert_outbox
                WHERE state = 'pending'
                """
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return max(0, int(float(row[0])))

    def list_recent(self, limit: int) -> list[dict[str, Any]]:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT alert_id, created_ts, alert_type, severity, symbol, timeframe,
                       dedupe_key, chat_id, state, attempt_count, last_error,
                       telegram_message_id, sent_ts, payload
                FROM alert.alert_outbox
                ORDER BY created_ts DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def claim_pending_for_send(self, limit: int) -> list[dict[str, Any]]:
        """Rows that are pending and chat is allowed + not muted."""
        import time as _time

        now_ms = int(_time.time() * 1000)
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute("BEGIN")
            rows = conn.execute(
                """
                SELECT o.alert_id, o.alert_type, o.severity, o.payload, o.chat_id,
                       o.attempt_count
                FROM alert.alert_outbox o
                INNER JOIN alert.chat_subscriptions s ON s.chat_id = o.chat_id
                WHERE o.state = 'pending'
                  AND s.status = 'allowed'
                  AND (s.muted_until_ts_ms IS NULL OR s.muted_until_ts_ms < %s)
                ORDER BY o.created_ts ASC
                LIMIT %s
                FOR UPDATE OF o SKIP LOCKED
                """,
                (now_ms, limit),
            ).fetchall()
            for r in rows:
                conn.execute(
                    """
                    UPDATE alert.alert_outbox
                    SET state = 'sending', attempt_count = attempt_count + 1
                    WHERE alert_id = %s::uuid
                    """,
                    (str(r["alert_id"]),),
                )
            conn.commit()
        return [dict(r) for r in rows]

    def mark_sent(
        self,
        alert_id: str,
        *,
        telegram_message_id: int | None,
        simulated: bool,
    ) -> None:
        state = "simulated" if simulated else "sent"
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                UPDATE alert.alert_outbox
                SET state = %s,
                    telegram_message_id = %s,
                    sent_ts = now(),
                    last_error = NULL
                WHERE alert_id = %s::uuid
                """,
                (state, telegram_message_id, alert_id),
            )
            conn.commit()

    def mark_failed(self, alert_id: str, err: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                UPDATE alert.alert_outbox
                SET state = 'failed', last_error = %s
                WHERE alert_id = %s::uuid
                """,
                (err[:2000], alert_id),
            )
            conn.commit()

    def requeue_send_or_fail(self, alert_id: str, err: str, *, max_attempts: int) -> None:
        """Nach fehlgeschlagenem Send: pending retry solange attempt_count < max_attempts."""
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT attempt_count FROM alert.alert_outbox
                WHERE alert_id = %s::uuid
                """,
                (alert_id,),
            ).fetchone()
            if row is None:
                return
            ac = int(row[0])
            if ac < max_attempts:
                conn.execute(
                    """
                    UPDATE alert.alert_outbox
                    SET state = 'pending', last_error = %s
                    WHERE alert_id = %s::uuid
                    """,
                    (err[:2000], alert_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE alert.alert_outbox
                    SET state = 'failed', last_error = %s
                    WHERE alert_id = %s::uuid
                    """,
                    (err[:2000], alert_id),
                )
            conn.commit()

    def requeue_sending_to_pending(self, alert_id: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                UPDATE alert.alert_outbox SET state = 'pending'
                WHERE alert_id = %s::uuid AND state = 'sending'
                """,
                (alert_id,),
            )
            conn.commit()

    def last_alert_summary(self, chat_id: int, types: tuple[str, ...]) -> str | None:
        if not types:
            return None
        placeholders = ",".join(["%s"] * len(types))
        sql = f"""
                SELECT payload FROM alert.alert_outbox
                WHERE chat_id = %s AND alert_type IN ({placeholders})
                ORDER BY created_ts DESC LIMIT 1
                """
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(sql, (chat_id, *types)).fetchone()
        if row is None:
            return None
        pl = row["payload"]
        if isinstance(pl, str):
            pl = json.loads(pl)
        if isinstance(pl, dict):
            return str(pl.get("text", pl))[:500]
        return None
