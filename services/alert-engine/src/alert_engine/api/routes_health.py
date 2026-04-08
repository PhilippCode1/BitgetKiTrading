from __future__ import annotations

import logging
from typing import Any

import psycopg
import redis
from fastapi import APIRouter
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    merge_ready_details,
)

from alert_engine.config import get_settings
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_state import RepoBotState
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from config.settings import _is_blank_or_placeholder
from shared_py.telegram_chat_contract import command_contract_summary

logger = logging.getLogger("alert_engine.health")

router = APIRouter(tags=["health"])


def _telegram_readiness(settings: Any) -> tuple[bool, str]:
    """Lokal/paper: ohne Token startfaehig (dry_run oder non-prod). Produktion: Token Pflicht."""
    token_missing = _is_blank_or_placeholder(settings.telegram_bot_token)
    if settings.telegram_dry_run:
        return True, f"mode={settings.telegram_mode} dry_run token_set={not token_missing}"
    if settings.production and token_missing:
        return False, "production_requires_TELEGRAM_BOT_TOKEN"
    if token_missing:
        return True, f"mode={settings.telegram_mode} token_missing_ok_non_production"
    return True, f"mode={settings.telegram_mode} token_configured"


def _check_db(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def _check_redis(url: str) -> bool:
    try:
        r = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        return bool(r.ping())
    except redis.RedisError:
        return False


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    db_ok = bool(settings.database_url) and _check_db(settings.database_url)
    redis_ok = bool(settings.redis_url) and _check_redis(settings.redis_url)
    last_uid = 0
    pending = 0
    failed = 0
    oldest_pending_age_ms: int | None = None
    subscribers_allowed: int | None = None
    if db_ok:
        try:
            outbox = RepoOutbox(settings.database_url)
            last_uid = RepoBotState(settings.database_url).get_last_update_id()
            pending = outbox.count_pending()
            failed = outbox.count_state("failed")
            oldest_pending_age_ms = outbox.oldest_pending_age_ms()
            subscribers_allowed = len(
                RepoSubscriptions(settings.database_url).list_allowed_chat_ids()
            )
        except Exception as exc:
            logger.warning("health db extra: %s", exc)
    return {
        "status": "ok" if db_ok and redis_ok and failed == 0 else "degraded",
        "db_ok": db_ok,
        "redis_ok": redis_ok,
        "telegram_mode": settings.telegram_mode,
        "dry_run": settings.telegram_dry_run,
        "last_update_id": last_uid,
        "outbox_pending": pending,
        "outbox_failed": failed,
        "oldest_pending_age_ms": oldest_pending_age_ms,
        "chat_subscribers_allowed": subscribers_allowed,
        "telegram_chat_contract": command_contract_summary(),
    }


@router.get("/ready")
def ready() -> dict[str, Any]:
    settings = get_settings()
    failed_ct = 0
    try:
        failed_ct = RepoOutbox(settings.database_url).count_state("failed")
    except Exception as exc:
        ob_ok = False
        ob_detail = str(exc)[:200]
    else:
        if settings.production:
            ob_ok = failed_ct == 0
            ob_detail = f"outbox_failed_messages={failed_ct}"
        else:
            # Lokal/paper: historische failed-Eintraege blockieren Compose-Health nicht
            ob_ok = True
            ob_detail = (
                f"outbox_failed_messages={failed_ct} "
                f"(non_production_not_blocking)"
            )
    tel_ok, tel_detail = _telegram_readiness(settings)
    parts = {
        "postgres": check_postgres(settings.database_url),
        "redis": check_redis_url(settings.redis_url),
        "telegram": (tel_ok, tel_detail),
        "outbox": (ob_ok, ob_detail),
    }
    parts = append_peer_readiness_checks(
        parts,
        settings.readiness_require_urls_raw,
        timeout_sec=float(settings.readiness_peer_timeout_sec),
    )
    ok, details = merge_ready_details(parts)
    return {"ready": ok, "checks": details}
