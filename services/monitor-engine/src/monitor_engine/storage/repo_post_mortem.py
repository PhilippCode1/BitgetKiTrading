from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

logger = logging.getLogger("monitor_engine.repo_post_mortem")


@dataclass(frozen=True)
class PostMortemRow:
    id: str
    created_ts: datetime
    trigger: str
    correlation_id: str | None
    started_ts: datetime
    completed_ts: datetime | None
    duration_ms: int | None
    redis_event_samples: Any
    service_health: Any
    llm_status: str | None
    llm_result: Any
    telegram_enqueued: bool
    report_url: str | None


def insert_post_mortem(
    dsn: str,
    *,
    post_mortem_id: str,
    trigger: str,
    correlation_id: str,
    started_ts: datetime,
    completed_ts: datetime,
    duration_ms: int,
    redis_event_samples: list[dict[str, Any]] | dict[str, Any],
    service_health: list[dict[str, Any]] | dict[str, Any],
    llm_status: str,
    llm_result: dict[str, Any] | None,
    telegram_enqueued: bool,
    report_url: str,
) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO ops.incident_post_mortems (
              id, trigger, correlation_id, started_ts, completed_ts, duration_ms,
              redis_event_samples, service_health, llm_status, llm_result,
              telegram_enqueued, report_url
            ) VALUES (
              %s, %s, %s, %s, %s, %s,
              %s::jsonb, %s::jsonb, %s, %s::jsonb,
              %s, %s
            )
            """,
            (
                post_mortem_id,
                trigger,
                correlation_id,
                started_ts,
                completed_ts,
                int(duration_ms),
                json.dumps(redis_event_samples),
                json.dumps(service_health),
                llm_status,
                json.dumps(llm_result) if llm_result is not None else None,
                telegram_enqueued,
                report_url,
            ),
        )
    logger.info("incident post_mortem written id=%s", post_mortem_id)


def update_telegram_enqueued(dsn: str, post_mortem_id: str, enqueued: bool) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            UPDATE ops.incident_post_mortems
            SET telegram_enqueued = %s
            WHERE id = %s::uuid
            """,
            (enqueued, post_mortem_id),
        )


def fetch_post_mortem(dsn: str, post_mortem_id: str) -> PostMortemRow | None:
    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                SELECT id, created_ts, trigger, correlation_id, started_ts, completed_ts,
                       duration_ms, redis_event_samples, service_health, llm_status, llm_result,
                       telegram_enqueued, report_url
                FROM ops.incident_post_mortems
                WHERE id = %s::uuid
                """,
                (post_mortem_id,),
            ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    if not row:
        return None
    d = dict(row)
    return PostMortemRow(
        id=str(d["id"]),
        created_ts=d["created_ts"],
        trigger=str(d["trigger"]),
        correlation_id=str(d["correlation_id"]) if d.get("correlation_id") else None,
        started_ts=d["started_ts"],
        completed_ts=d.get("completed_ts"),
        duration_ms=int(d["duration_ms"]) if d.get("duration_ms") is not None else None,
        redis_event_samples=d.get("redis_event_samples"),
        service_health=d.get("service_health"),
        llm_status=str(d["llm_status"]) if d.get("llm_status") else None,
        llm_result=d.get("llm_result"),
        telegram_enqueued=bool(d.get("telegram_enqueued")),
        report_url=str(d["report_url"]) if d.get("report_url") else None,
    )


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=UTC)
