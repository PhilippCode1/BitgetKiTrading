from __future__ import annotations

import json
from typing import Any

import psycopg


class RepoAudit:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def log_command(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        command: str,
        args: dict[str, Any],
    ) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.command_audit (chat_id, user_id, command, args)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (chat_id, user_id, command, json.dumps(args)),
            )
            conn.commit()
