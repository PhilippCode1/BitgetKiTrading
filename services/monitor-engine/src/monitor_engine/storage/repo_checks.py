from __future__ import annotations

import json
import logging

import psycopg
from psycopg import errors as pg_errors

from monitor_engine.checks.data_freshness import FreshnessRow
from monitor_engine.checks.redis_streams import StreamGroupCheckResult
from monitor_engine.checks.services_http import ServiceCheckResult

logger = logging.getLogger("monitor_engine.repo_checks")


def insert_service_checks(dsn: str, rows: list[ServiceCheckResult]) -> None:
    if not rows:
        return
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for r in rows:
                    try:
                        cur.execute(
                            """
                            INSERT INTO ops.service_checks
                            (service_name, check_type, status, latency_ms, details)
                            VALUES (%s, %s, %s, %s, %s::jsonb)
                            """,
                            (
                                r.service_name,
                                r.check_type,
                                r.status,
                                r.latency_ms,
                                json.dumps(r.details),
                            ),
                        )
                    except pg_errors.Error as exc:
                        logger.warning(
                            "service_checks insert skipped service=%s check_type=%s: %s",
                            r.service_name,
                            r.check_type,
                            exc,
                        )
    except pg_errors.Error as exc:
        logger.warning("service_checks batch connect/tx failed: %s", exc)


def insert_stream_checks(dsn: str, rows: list[StreamGroupCheckResult]) -> None:
    if not rows:
        return
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for r in rows:
                    try:
                        cur.execute(
                            """
                            INSERT INTO ops.stream_checks
                            (stream, group_name, pending_count, lag, last_generated_id,
                             last_delivered_id, status, details)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                            """,
                            (
                                r.stream,
                                r.group_name,
                                r.pending_count,
                                r.lag,
                                r.last_generated_id,
                                r.last_delivered_id,
                                r.status,
                                json.dumps(r.details),
                            ),
                        )
                    except pg_errors.Error as exc:
                        logger.warning(
                            "stream_checks insert skipped stream=%s group=%s: %s",
                            r.stream,
                            r.group_name,
                            exc,
                        )
    except pg_errors.Error as exc:
        logger.warning("stream_checks batch connect/tx failed: %s", exc)


def insert_data_freshness(dsn: str, rows: list[FreshnessRow]) -> None:
    if not rows:
        return
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for r in rows:
                    try:
                        cur.execute(
                            """
                            INSERT INTO ops.data_freshness
                            (datapoint, last_ts_ms, age_ms, status, details)
                            VALUES (%s, %s, %s, %s, %s::jsonb)
                            """,
                            (
                                r.datapoint,
                                r.last_ts_ms,
                                r.age_ms,
                                r.status,
                                json.dumps(r.details),
                            ),
                        )
                    except pg_errors.Error as exc:
                        logger.warning(
                            "data_freshness insert skipped datapoint=%s: %s",
                            r.datapoint,
                            exc,
                        )
    except pg_errors.Error as exc:
        logger.warning("data_freshness batch connect/tx failed: %s", exc)


def insert_incident(
    dsn: str,
    summary: str,
    related_keys: list[str],
) -> None:
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ops.incidents (summary, related_alert_keys)
                VALUES (%s, %s::jsonb)
                """,
                (summary, json.dumps(related_keys)),
            )
