from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import psycopg
import psycopg.errors
from psycopg.rows import dict_row

from alert_engine.config import Settings
from alert_engine.log_safety import safe_chat_ref, safe_user_ref
from shared_py.telegram_chat_contract import TELEGRAM_CHAT_CONTRACT_VERSION
from alert_engine.storage.repo_audit import RepoAudit
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from alert_engine.storage.repo_telegram_operator import RepoTelegramOperator
from alert_engine.telegram.api_client import TelegramApiClient
from shared_py.customer_telegram_notify import enqueue_customer_notify
from shared_py.customer_telegram_prefs import (
    DEFAULT_PREFS,
    NOTIFY_PREFS_ORDERED_BOOL_KEYS,
    audit_prefs_changed,
    fetch_notify_prefs_merged,
    upsert_notify_prefs,
)
from shared_py.customer_telegram_repo import (
    fetch_tenant_customer_lifecycle_minimal,
    get_tenant_id_for_chat,
    try_complete_customer_start_link,
)

logger = logging.getLogger("alert_engine.commands")

# Explizite Allowlist: keine freien Text-Befehle, keine Strategie-/Policy-Mutation.
READONLY_TELEGRAM_COMMANDS: frozenset[str] = frozenset(
    {
        "/help",
        "/status",
        "/mute",
        "/unmute",
        "/lastsignal",
        "/lastnews",
    }
)
OPERATOR_TELEGRAM_COMMANDS: frozenset[str] = frozenset(
    {
        "/exec_recent",
        "/exec_show",
        "/release_step1",
        "/release_confirm",
        "/release_abort",
        "/emerg_step1",
        "/emerg_confirm",
        "/emerg_abort",
    }
)
ALLOWED_TELEGRAM_COMMANDS: frozenset[str] = (
    READONLY_TELEGRAM_COMMANDS | OPERATOR_TELEGRAM_COMMANDS | frozenset({"/start"})
)

# Kunden-Chat (Binding): vor Operator-Whitelist; keine Strategie-Mutation.
CUSTOMER_PORTAL_COMMANDS: frozenset[str] = frozenset(
    {"/konto", "/prefs", "/set_notify", "/tip", "/kunde_help"}
)


@dataclass
class CommandContext:
    settings: Settings
    subs: RepoSubscriptions
    audit: RepoAudit
    outbox: RepoOutbox
    api: TelegramApiClient
    redis_ok: bool
    db_ok: bool
    pending_outbox: int
    tg_operator: RepoTelegramOperator


def _parse_notify_bool_token(token: str) -> bool | None:
    t = token.strip().lower()
    if t in ("on", "true", "1", "ja", "an", "yes"):
        return True
    if t in ("off", "false", "0", "nein", "aus", "no"):
        return False
    return None


def _dispatch_customer_portal_command(
    ctx: CommandContext,
    chat_id: int,
    user_id: Any,
    cmd: str,
    arg: str,
) -> None:
    dsn = (ctx.settings.database_url or "").strip()
    if not dsn:
        ctx.api.send_message(chat_id, "Diese Funktion ist derzeit nicht verfuegbar.")
        return

    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            tenant_id = get_tenant_id_for_chat(conn, telegram_chat_id=chat_id)
    except Exception as exc:
        logger.exception("customer portal cmd lookup: %s", exc)
        ctx.api.send_message(
            chat_id,
            "Datenbank nicht erreichbar. Bitte spaeter erneut versuchen.",
        )
        return

    if tenant_id is None and cmd != "/kunde_help":
        ctx.api.send_message(
            chat_id,
            "Kein Kundenkonto verknuepft. Bitte im Web-Kundenbereich unter Telegram einen "
            "Link erzeugen und hier mit /start link_<token> bestaetigen.",
        )
        ctx.audit.log_command(
            chat_id=chat_id,
            user_id=int(user_id) if user_id else None,
            command="customer_cmd_no_binding",
            args={"attempted": cmd},
        )
        return

    ctx.audit.log_command(
        chat_id=chat_id,
        user_id=int(user_id) if user_id else None,
        command=cmd,
        args={"arg": arg[:300], "chat_contract_version": TELEGRAM_CHAT_CONTRACT_VERSION},
    )

    if cmd == "/kunde_help":
        lines = [
            "Kunden-Bot (Lesen und Benachrichtigungs-Präferenzen):",
            "/konto — Kurzinfo Lebenszyklus",
            "/prefs — Benachrichtigungsarten",
            "/set_notify <schluessel> <an|aus> — z. B. notify_billing aus",
            "/tip — Hinweis KI/Assist im Kundenbereich",
            "Pflicht-Hinweise (Konto, Verknuepfung, Test) werden immer zugestellt.",
        ]
        ctx.api.send_message(chat_id, "\n".join(lines))
        return

    assert tenant_id is not None

    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            if cmd == "/prefs":
                try:
                    prefs = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
                except psycopg.errors.UndefinedTable:
                    prefs = dict(DEFAULT_PREFS)
                lines = ["Benachrichtigungen (an/aus):"] + [
                    f"- {k}: {'an' if prefs.get(k) else 'aus'}" for k in NOTIFY_PREFS_ORDERED_BOOL_KEYS
                ]
                ctx.api.send_message(chat_id, "\n".join(lines))
            elif cmd == "/set_notify":
                parts = arg.split()
                if len(parts) != 2:
                    ctx.api.send_message(
                        chat_id,
                        "Syntax: /set_notify <schluessel> <an|aus>\n"
                        f"Schluessel: {', '.join(NOTIFY_PREFS_ORDERED_BOOL_KEYS)}",
                    )
                    return
                key, tok = parts[0].strip(), parts[1].strip()
                if key not in NOTIFY_PREFS_ORDERED_BOOL_KEYS:
                    ctx.api.send_message(
                        chat_id,
                        "Unbekannter Schluessel. Erlaubt: " + ", ".join(NOTIFY_PREFS_ORDERED_BOOL_KEYS),
                    )
                    return
                b = _parse_notify_bool_token(tok)
                if b is None:
                    ctx.api.send_message(chat_id, "Zweites Argument: an oder aus (oder true/false).")
                    return
                try:
                    before = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
                    with conn.transaction():
                        after = upsert_notify_prefs(conn, tenant_id=tenant_id, **{key: b})
                        audit_prefs_changed(
                            conn,
                            tenant_id=tenant_id,
                            actor="telegram_bot",
                            detail={"before": before, "after": after, "key": key},
                        )
                except psycopg.errors.UndefinedTable:
                    ctx.api.send_message(
                        chat_id,
                        "Einstellungen nicht verfuegbar — bitte Datenbank-Migration 613 anwenden.",
                    )
                    return
                ctx.api.send_message(
                    chat_id,
                    f"Gespeichert: {key}={'an' if after.get(key) else 'aus'}.",
                )
            elif cmd == "/konto":
                row = fetch_tenant_customer_lifecycle_minimal(conn, tenant_id=tenant_id)
                if not row:
                    ctx.api.send_message(
                        chat_id,
                        "Keine Lebenszyklus-Daten gefunden. Status siehe Web-Kundenbereich.",
                    )
                else:
                    te = row.get("trial_ends_at")
                    te_s = te.isoformat() if hasattr(te, "isoformat") else (str(te) if te else "—")
                    ctx.api.send_message(
                        chat_id,
                        "Konto (Kurz):\n"
                        f"- Status: {row.get('lifecycle_status')}\n"
                        f"- E-Mail verifiziert: {'ja' if row.get('email_verified') else 'nein'}\n"
                        f"- Trial bis: {te_s}",
                    )
            elif cmd == "/tip":
                ctx.api.send_message(
                    chat_id,
                    "KI-Zusammenfassungen und Assist: bitte im Web-Kundenbereich "
                    "(Konsole → Konto) den KI-Assistenten oder die Hilfe-Bereiche oeffnen. "
                    "Hier werden keine automatischen KI-Antworten erzeugt.",
                )
    except Exception as exc:
        logger.exception("customer portal cmd: %s", exc)
        ctx.api.send_message(chat_id, "Interner Fehler. Bitte spaeter erneut versuchen.")


def _customer_link_error_de(err: str) -> str:
    return {
        "empty_token": "Der Verknuepfungs-Link ist ungueltig. Bitte im Kundenbereich einen neuen Link erzeugen.",
        "unknown_token": "Unbekannter oder abgelaufener Link. Bitte im Kundenbereich einen neuen Link anfordern.",
        "token_used": "Dieser Link wurde bereits verwendet. Bitte im Kundenbereich einen neuen Link erzeugen.",
        "expired": "Der Link ist abgelaufen. Bitte im Kundenbereich einen neuen Link erzeugen.",
        "chat_bound_other_tenant": (
            "Dieser Telegram-Chat ist bereits mit einem anderen Konto verknuepft. "
            "Bitte einen anderen Chat nutzen oder den Support kontaktieren."
        ),
    }.get(
        err,
        "Verknuepfung fehlgeschlagen. Bitte erneut im Kundenbereich einen Link erzeugen oder den Support kontaktieren.",
    )


def _handle_customer_start_link(
    ctx: CommandContext,
    chat_id: int,
    user_id: Any,
    username: Any,
    title: Any,
    start_arg: str,
) -> None:
    dsn = (ctx.settings.database_url or "").strip()
    if not dsn:
        ctx.api.send_message(
            chat_id,
            "Telegram-Verknuepfung ist derzeit nicht moeglich (Dienst-Konfiguration).",
        )
        return
    uname = str(username) if username else None
    ttitle = str(title) if title else None
    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.transaction():
                res = try_complete_customer_start_link(
                    conn,
                    start_arg=start_arg,
                    telegram_chat_id=chat_id,
                    telegram_username=uname,
                )
                if not res.get("ok"):
                    err = str(res.get("error") or "failed")
                    ctx.api.send_message(chat_id, _customer_link_error_de(err))
                    ctx.audit.log_command(
                        chat_id=chat_id,
                        user_id=int(user_id) if user_id else None,
                        command="start_customer_link_failed",
                        args={"error": err},
                    )
                    return
                tid = str(res.get("tenant_id") or "")
                enqueue_customer_notify(
                    conn,
                    tenant_id=tid,
                    text=(
                        "Ihr Kundenkonto ist per Telegram erreichbar: Pflicht-Benachrichtigungen "
                        "(Guthaben, Trades, Risiko) werden an diesen Chat gesendet. "
                        "/kunde_help zeigt Befehle fuer Einstellungen."
                    ),
                    category="telegram_link_ok",
                    severity="info",
                    dedupe_key=f"telegram_link_ok:{tid}",
                    audit_actor="telegram_bot",
                )
    except Exception as exc:
        logger.exception("customer start link db error: %s", exc)
        ctx.api.send_message(
            chat_id,
            "Interner Fehler bei der Verknuepfung. Bitte spaeter erneut versuchen.",
        )
        return
    ctx.audit.log_command(
        chat_id=chat_id,
        user_id=int(user_id) if user_id else None,
        command="/start",
        args={"customer_link": "ok", "title": ttitle},
    )
    ctx.api.send_message(
        chat_id,
        "Erfolg: Dieser Chat ist mit Ihrem Kundenkonto verknuepft. "
        "Sie erhalten kuenftig Pflicht-Hinweise zu Konto, Einzahlungen, Guthaben und Risiko. "
        "/help zeigt Operator-Befehle, sofern Ihr Chat freigeschaltet ist.",
    )


def handle_update(raw: dict[str, Any], ctx: CommandContext) -> None:
    msg = raw.get("message") or raw.get("edited_message")
    if not isinstance(msg, dict):
        return
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    chat_id = int(chat_id)
    user = msg.get("from") or {}
    user_id = user.get("id")
    username = user.get("username")
    title = chat.get("title")
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].split("@", 1)[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/start" and arg.lower().startswith("link_"):
        _handle_customer_start_link(ctx, chat_id, user_id, username, title, arg)
        return

    if cmd in CUSTOMER_PORTAL_COMMANDS:
        _dispatch_customer_portal_command(ctx, chat_id, user_id, cmd, arg)
        return

    env_ids = ctx.settings.parsed_allowed_chat_ids()
    in_env = chat_id in env_ids
    chat_ref = safe_chat_ref(chat_id)
    user_ref = safe_user_ref(user_id)

    if env_ids and not in_env:
        ctx.audit.log_command(
            chat_id=chat_id,
            user_id=int(user_id) if user_id is not None else None,
            command="ignored_not_whitelisted",
            args={"attempted": cmd},
        )
        logger.info("ignored update from %s (%s not whitelisted)", chat_ref, user_ref)
        return

    if cmd == "/start":
        force_allowed = bool(env_ids) and in_env
        status = ctx.subs.upsert_start(
            chat_id,
            int(user_id) if user_id is not None else None,
            str(username) if username else None,
            str(title) if title else None,
            force_allowed=force_allowed,
        )
        ctx.audit.log_command(chat_id=chat_id, user_id=int(user_id) if user_id else None, command=cmd, args={})
        if force_allowed or status == "allowed":
            reply = "Willkommen. Du bist freigeschaltet. /help fuer Befehle."
        elif not env_ids:
            reply = "Anfrage gespeichert (pending). Admin muss Chat freigeben."
        else:
            reply = "Konfigurationsfehler: Chat sollte erlaubt sein."
        ctx.api.send_message(chat_id, reply)
        return

    st = ctx.subs.get_status(chat_id)
    allowed = st == "allowed" or (bool(env_ids) and in_env)
    if not allowed:
        ctx.audit.log_command(
            chat_id=chat_id,
            user_id=int(user_id) if user_id else None,
            command="ignored_pending",
            args={"attempted": cmd},
        )
        return

    if cmd not in ALLOWED_TELEGRAM_COMMANDS:
        raw_prefix = text[:500]
        ctx.audit.log_command(
            chat_id=chat_id,
            user_id=int(user_id) if user_id else None,
            command="rejected_forbidden_command",
            args={"attempted": cmd, "raw_prefix": raw_prefix},
        )
        ctx.tg_operator.log_action(
            outcome="rejected_forbidden_command",
            chat_id=chat_id,
            user_id=int(user_id) if user_id is not None else None,
            details={"attempted": cmd, "raw_prefix": raw_prefix},
        )
        ctx.api.send_message(
            chat_id,
            "Unzulaessiger Befehl. Telegram darf keine Strategieparameter, Playbooks, "
            "Gewichte, Risk-Limits oder Routing aendern. Nur /help und freigegebene "
            "Lese-/Operator-Befehle.",
        )
        logger.info("rejected forbidden telegram cmd=%s %s %s", cmd, chat_ref, user_ref)
        return

    ctx.audit.log_command(
        chat_id=chat_id,
        user_id=int(user_id) if user_id else None,
        command=cmd,
        args={"arg": arg, "chat_contract_version": TELEGRAM_CHAT_CONTRACT_VERSION},
    )

    if cmd in OPERATOR_TELEGRAM_COMMANDS:
        from alert_engine.telegram.operator_actions import dispatch_operator_command

        dispatch_operator_command(cmd, arg, chat_id, int(user_id) if user_id else None, ctx)
        return

    if cmd == "/help":
        lines = [
            f"Chat-Vertrag: {TELEGRAM_CHAT_CONTRACT_VERSION}",
            "Keine Strategie-/Policy-Mutation via Chat (Gewichte, Playbooks, Risk-Caps, Registry, Prompts).",
            "Lesezugriff: /status /mute [min] /unmute /lastsignal /lastnews",
            "Operator (TELEGRAM_OPERATOR_ACTIONS_ENABLED + Live-Broker; optional RBAC user-IDs + Manual-Token):",
            "  /exec_recent [n]  /exec_show <execution_uuid>",
            "  Freigabe: /release_step1 <execution_uuid> -> /release_confirm <pending> <code> [<manual_token>]",
            "  Abbrechen: /release_abort <pending_uuid>",
            "  Notfall (nur existierende internal_order_id):",
            "  /emerg_step1 <uuid> -> /emerg_confirm <pending> <code> [<manual_token>] ; /emerg_abort <pending>",
        ]
        ctx.api.send_message(chat_id, "\n".join(lines))
    elif cmd == "/status":
        ctx.api.send_message(
            chat_id,
            f"db_ok={ctx.db_ok} redis_ok={ctx.redis_ok} pending_outbox={ctx.pending_outbox} "
            f"dry_run={ctx.settings.telegram_dry_run} "
            f"operator_actions={ctx.settings.telegram_operator_actions_enabled}",
        )
    elif cmd == "/mute":
        mins = int(arg) if arg.isdigit() else 60
        until = int(time.time() * 1000) + mins * 60 * 1000
        ctx.subs.set_mute(chat_id, until)
        ctx.api.send_message(chat_id, f"Stumm bis ts_ms={until} ({mins} min).")
    elif cmd == "/unmute":
        ctx.subs.set_mute(chat_id, None)
        ctx.api.send_message(chat_id, "Stumm aufgehoben.")
    elif cmd == "/lastsignal":
        s = ctx.outbox.last_alert_summary(chat_id, ("GROSS_SIGNAL", "CORE_SIGNAL"))
        ctx.api.send_message(chat_id, s or "Keine Signal-Alerts in der Outbox fuer diesen Chat.")
    elif cmd == "/lastnews":
        s = ctx.outbox.last_alert_summary(chat_id, ("NEWS_HIGH",))
        ctx.api.send_message(chat_id, s or "Keine News-Alerts.")
