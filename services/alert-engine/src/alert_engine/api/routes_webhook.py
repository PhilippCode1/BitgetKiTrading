from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from alert_engine.config import get_settings
from alert_engine.storage.repo_audit import RepoAudit
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from alert_engine.storage.repo_telegram_operator import RepoTelegramOperator
from alert_engine.telegram.api_client import TelegramApiClient
from alert_engine.telegram.commands import CommandContext, handle_update

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _build_command_context(request: Request) -> CommandContext:
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
    return CommandContext(
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


@router.post("/webhook")
def telegram_webhook(
    request: Request,
    body: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict[str, Any]:
    settings = get_settings()
    if settings.telegram_mode != "webhook":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TELEGRAM_WEBHOOK_DISABLED",
                "message": "TELEGRAM_MODE ist nicht auf webhook gesetzt.",
            },
        )
    expected = settings.telegram_webhook_secret.strip()
    presented = str(x_telegram_bot_api_secret_token or "").strip()
    if not expected or presented != expected:
        raise HTTPException(status_code=401, detail="invalid telegram webhook secret")
    handle_update(body, _build_command_context(request))
    return {"ok": True}
