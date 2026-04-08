from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row

from shared_py.telegram_chat_contract import TELEGRAM_CHAT_CONTRACT_VERSION

Outcome = Literal[
    "rejected_forbidden_command",
    "rejected_invalid_args",
    "rejected_not_enabled",
    "rejected_not_eligible",
    "rejected_expired",
    "rejected_bad_code",
    "rejected_wrong_chat",
    "rejected_http_error",
    "rejected_missing_upstream",
    "rejected_rbac",
    "rejected_manual_token",
    "pending_created",
    "pending_cancelled",
    "executed_ok",
    "executed_error",
]

ActionKind = Literal["operator_release", "emergency_flatten"]


class RepoTelegramOperator:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def log_action(
        self,
        *,
        outcome: Outcome,
        chat_id: int | None,
        user_id: int | None,
        action_kind: str | None = None,
        execution_id: str | None = None,
        pending_id: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
        chat_contract_version: str | None = None,
        rbac_scope: str | None = None,
        manual_action_token_fp: str | None = None,
    ) -> uuid.UUID:
        aid = uuid.uuid4()
        cv = chat_contract_version or TELEGRAM_CHAT_CONTRACT_VERSION
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.operator_action_audit (
                    audit_id, outcome, chat_id, user_id, action_kind,
                    execution_id, pending_id, http_status, details_json,
                    chat_contract_version, rbac_scope, manual_action_token_fp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    str(aid),
                    outcome,
                    chat_id,
                    user_id,
                    action_kind,
                    execution_id,
                    pending_id,
                    http_status,
                    json.dumps(details or {}),
                    cv,
                    rbac_scope,
                    manual_action_token_fp,
                ),
            )
            conn.commit()
        return aid

    def insert_pending(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        action_kind: ActionKind,
        execution_id: str | None,
        request_body_json: dict[str, Any],
        summary_redacted: str,
        confirm_code_hash: str,
        ttl_sec: int,
    ) -> uuid.UUID:
        pid = uuid.uuid4()
        exp = datetime.now(tz=UTC) + timedelta(seconds=max(60, int(ttl_sec)))
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.telegram_operator_pending (
                    pending_id, chat_id, user_id, action_kind, execution_id,
                    request_body_json, summary_redacted, confirm_code_hash, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(pid),
                    chat_id,
                    user_id,
                    action_kind,
                    execution_id,
                    json.dumps(request_body_json),
                    summary_redacted[:4000],
                    confirm_code_hash,
                    exp,
                ),
            )
            conn.commit()
        return pid

    def get_open_pending(self, pending_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                SELECT pending_id, chat_id, user_id, action_kind, execution_id,
                       request_body_json, summary_redacted, confirm_code_hash,
                       expires_at, consumed_at, created_ts
                FROM alert.telegram_operator_pending
                WHERE pending_id = %s AND consumed_at IS NULL
                """,
                (pending_id,),
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if isinstance(d.get("request_body_json"), str):
            try:
                d["request_body_json"] = json.loads(d["request_body_json"])
            except json.JSONDecodeError:
                d["request_body_json"] = {}
        return d

    def mark_consumed(self, pending_id: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            cur = conn.execute(
                """
                UPDATE alert.telegram_operator_pending
                SET consumed_at = now()
                WHERE pending_id = %s AND consumed_at IS NULL
                """,
                (pending_id,),
            )
            n = cur.rowcount
            conn.commit()
        return n > 0
