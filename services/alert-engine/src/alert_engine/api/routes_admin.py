from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from shared_py.eventbus import EventEnvelope
from shared_py.service_auth import assert_internal_service_auth

from alert_engine.config import get_settings
from alert_engine.storage.repo_audit import RepoAudit
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from alert_engine.storage.repo_telegram_operator import RepoTelegramOperator
from alert_engine.telegram.api_client import TelegramApiClient
from alert_engine.telegram.commands import CommandContext, handle_update
from alert_engine.worker.event_consumer import apply_envelope_admin

logger = logging.getLogger("alert_engine.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(
    x_admin_token: str | None,
    x_internal_service_key: str | None,
) -> None:
    s = get_settings()
    assert_internal_service_auth(s, x_internal_service_key)
    exp = s.admin_token.strip()
    if not exp:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN not configured")
    if not x_admin_token or x_admin_token.strip() != exp:
        raise HTTPException(status_code=401, detail="unauthorized")


def _require_alert_replay_enabled() -> None:
    s = get_settings()
    if s.security_allow_alert_replay_routes:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "ALERT_REPLAY_DISABLED",
            "message": (
                "Replay-Routen sind deaktiviert. Nur lokale/Test-Profile duerfen "
                "SECURITY_ALLOW_ALERT_REPLAY_ROUTES=true setzen."
            ),
        },
    )


class TestAlertBody(BaseModel):
    chat_id: int | None = None
    text: str = Field(default="Test alert from admin")


@router.post("/chats/{chat_id}/allow")
def admin_allow_chat(
    chat_id: int,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> dict[str, Any]:
    _require_admin(x_admin_token, x_internal_service_key)
    subs = RepoSubscriptions(get_settings().database_url)
    subs.upsert_chat_status(chat_id, "allowed")
    return {"ok": True, "chat_id": chat_id, "status": "allowed"}


@router.post("/chats/{chat_id}/block")
def admin_block_chat(
    chat_id: int,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> dict[str, Any]:
    _require_admin(x_admin_token, x_internal_service_key)
    subs = RepoSubscriptions(get_settings().database_url)
    subs.set_status(chat_id, "blocked")
    return {"ok": True, "chat_id": chat_id, "status": "blocked"}


@router.post("/test-alert")
def admin_test_alert(
    body: TestAlertBody,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> dict[str, Any]:
    _require_admin(x_admin_token, x_internal_service_key)
    settings = get_settings()
    subs = RepoSubscriptions(settings.database_url)
    outbox = RepoOutbox(settings.database_url)
    cid = body.chat_id
    if cid is None:
        chats = subs.list_allowed_chat_ids()
        if not chats:
            raise HTTPException(status_code=400, detail="no allowed chats; pass chat_id")
        cid = chats[0]
    aid = outbox.insert_pending(
        alert_type="SYSTEM_ALERT",
        severity="info",
        symbol=None,
        timeframe=None,
        dedupe_key=None,
        chat_id=cid,
        payload={"text": body.text, "source": "admin_test"},
    )
    return {"ok": True, "alert_id": aid, "chat_id": cid}


@router.post("/replay-event")
def admin_replay_event(
    body: dict[str, Any],
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> dict[str, Any]:
    _require_admin(x_admin_token, x_internal_service_key)
    _require_alert_replay_enabled()
    env = EventEnvelope.model_validate(body)
    apply_envelope_admin(env, get_settings())
    logger.info("admin replay-event type=%s", env.event_type)
    return {"ok": True, "event_type": env.event_type}


@router.post("/replay-telegram")
def admin_replay_telegram(
    request: Request,
    body: dict[str, Any],
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> dict[str, Any]:
    _require_admin(x_admin_token, x_internal_service_key)
    _require_alert_replay_enabled()
    settings = get_settings()
    api = TelegramApiClient(settings)
    subs = RepoSubscriptions(settings.database_url)
    audit = RepoAudit(settings.database_url)
    outbox = RepoOutbox(settings.database_url)
    tg_op = RepoTelegramOperator(settings.database_url)
    worker = getattr(request.app.state, "worker", None)
    r_ok, d_ok, pend = (
        worker.status.snapshot()
        if worker is not None
        else (False, True, outbox.count_pending())
    )
    ctx = CommandContext(
        settings=settings,
        subs=subs,
        audit=audit,
        outbox=outbox,
        api=api,
        redis_ok=r_ok,
        db_ok=d_ok,
        pending_outbox=pend,
        tg_operator=tg_op,
    )
    handle_update(body, ctx)
    return {"ok": True}
