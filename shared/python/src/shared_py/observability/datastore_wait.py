"""
Gemeinsames Warten auf Postgres/Redis vor App-Start (Backoff, klare Logs).
"""

from __future__ import annotations

import logging
import os
import time
import psycopg
import redis


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def wait_for_postgres(
    dsn: str,
    *,
    logger: logging.Logger | None = None,
    timeout_sec: int | None = None,
    label: str = "postgres",
) -> None:
    """Blockiert bis `select 1` oder Timeout."""
    log = logger or logging.getLogger("datastore_wait")
    limit = timeout_sec if timeout_sec is not None else _env_int("DATASTORE_WAIT_TIMEOUT_SEC", 120)
    deadline = time.monotonic() + float(limit)
    attempt = 0
    last_err: str | None = None
    while time.monotonic() < deadline:
        attempt += 1
        try:
            with psycopg.connect(dsn.strip(), connect_timeout=5, autocommit=True) as conn:
                conn.execute("select 1")
            log.info("%s ready after %s attempt(s)", label, attempt)
            return
        except Exception as exc:
            last_err = str(exc).split("\n", 1)[0][:200]
            sleep_s = min(5.0, 0.5 + 0.25 * min(attempt, 12))
            log.warning(
                "%s not ready (attempt %s, retry in %.1fs): %s",
                label,
                attempt,
                sleep_s,
                last_err,
            )
            time.sleep(sleep_s)
    raise RuntimeError(f"{label} nicht bereit nach {limit}s: {last_err}")


def wait_for_redis(
    url: str,
    *,
    logger: logging.Logger | None = None,
    timeout_sec: int | None = None,
    label: str = "redis",
) -> None:
    log = logger or logging.getLogger("datastore_wait")
    limit = timeout_sec if timeout_sec is not None else _env_int("DATASTORE_WAIT_TIMEOUT_SEC", 120)
    deadline = time.monotonic() + float(limit)
    attempt = 0
    last_err: str | None = None
    while time.monotonic() < deadline:
        attempt += 1
        try:
            client = redis.Redis.from_url(
                url.strip(),
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            if client.ping():
                log.info("%s ready after %s attempt(s)", label, attempt)
                return
        except Exception as exc:
            last_err = str(exc).split("\n", 1)[0][:200]
            sleep_s = min(5.0, 0.5 + 0.25 * min(attempt, 12))
            log.warning(
                "%s not ready (attempt %s, retry in %.1fs): %s",
                label,
                attempt,
                sleep_s,
                last_err,
            )
            time.sleep(sleep_s)
    raise RuntimeError(f"{label} nicht bereit nach {limit}s: {last_err}")


def wait_for_datastores(
    database_url: str,
    redis_url: str,
    *,
    logger: logging.Logger | None = None,
    timeout_sec: int | None = None,
    service_name: str = "app",
) -> None:
    """
    Wartet sequentiell auf Postgres und Redis. Aktivierbar per SKIP_DATASTORE_WAIT=1 (Tests/Notfall).
    """
    if (os.environ.get("SKIP_DATASTORE_WAIT") or "").strip().lower() in ("1", "true", "yes"):
        return
    log = logger or logging.getLogger("datastore_wait")
    log.info("datastore_wait start service=%s", service_name)
    du = (database_url or "").strip()
    ru = (redis_url or "").strip()
    if not du:
        raise RuntimeError("DATABASE_URL fehlt fuer datastore_wait")
    if not ru:
        raise RuntimeError("REDIS_URL fehlt fuer datastore_wait")
    wait_for_postgres(du, logger=log, timeout_sec=timeout_sec, label="postgres")
    wait_for_redis(ru, logger=log, timeout_sec=timeout_sec, label="redis")
    log.info("datastore_wait done service=%s", service_name)
