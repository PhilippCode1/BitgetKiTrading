from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from alert_engine.telegram.governance import manual_confirm_token_verify, operator_user_allowed
from alert_engine.telegram.live_broker_client import LiveBrokerOpsClient

if TYPE_CHECKING:
    from alert_engine.telegram.commands import CommandContext

logger = logging.getLogger("alert_engine.operator_actions")


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _fmt_summary_block(data: dict[str, Any]) -> str:
    s = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    lines = [
        f"execution_id={data.get('execution_id')}",
        f"eligible={data.get('eligible')}",
        f"reason={data.get('reason')}",
    ]
    for k in (
        "symbol",
        "direction",
        "decision_action",
        "decision_reason",
        "effective_runtime_mode",
        "source_signal_id",
        "leverage",
    ):
        if s.get(k) is not None:
            lines.append(f"{k}={s.get(k)}")
    return "\n".join(lines)


def dispatch_operator_command(
    cmd: str,
    arg: str,
    chat_id: int,
    user_id: int | None,
    ctx: CommandContext,
) -> None:
    assert ctx.tg_operator is not None
    op = ctx.tg_operator
    settings = ctx.settings
    api = ctx.api

    if not settings.telegram_operator_actions_enabled:
        op.log_action(
            outcome="rejected_not_enabled",
            chat_id=chat_id,
            user_id=user_id,
            details={"cmd": cmd},
        )
        api.send_message(
            chat_id,
            "Operator-Aktionen sind deaktiviert (TELEGRAM_OPERATOR_ACTIONS_ENABLED=false).",
        )
        return

    lb = LiveBrokerOpsClient(settings)
    if not lb.configured():
        op.log_action(
            outcome="rejected_missing_upstream",
            chat_id=chat_id,
            user_id=user_id,
            details={"cmd": cmd},
        )
        api.send_message(
            chat_id,
            "Live-Broker-Anbindung unvollstaendig: ALERT_ENGINE_LIVE_BROKER_BASE_URL und "
            "INTERNAL_API_KEY muessen gesetzt sein.",
        )
        return

    rbac_ok, rbac_scope = operator_user_allowed(
        user_id=user_id,
        allowed_ids=settings.parsed_operator_user_ids(),
    )
    if not rbac_ok:
        op.log_action(
            outcome="rejected_rbac",
            chat_id=chat_id,
            user_id=user_id,
            details={"cmd": cmd, "rbac_scope": rbac_scope},
            rbac_scope=rbac_scope,
        )
        api.send_message(
            chat_id,
            "RBAC: Deine Telegram-User-ID ist fuer Operator-Befehle nicht freigeschaltet "
            "(TELEGRAM_OPERATOR_ALLOWED_USER_IDS).",
        )
        return

    if cmd == "/exec_recent":
        lim = 10
        if arg.isdigit():
            lim = max(1, min(25, int(arg)))
        status, data = lb.get_recent_decisions(lim)
        if status != 200:
            op.log_action(
                outcome="rejected_http_error",
                chat_id=chat_id,
                user_id=user_id,
                http_status=status or None,
                details={"cmd": cmd, "body_keys": list(data.keys()) if isinstance(data, dict) else []},
            )
            api.send_message(chat_id, f"Upstream-Fehler decisions/recent http={status}")
            return
        items = data.get("items") if isinstance(data.get("items"), list) else []
        lines_out: list[str] = []
        for it in items[:lim]:
            if not isinstance(it, dict):
                continue
            eid = it.get("execution_id")
            lines_out.append(
                f"{eid} | {it.get('symbol')} | {it.get('decision_action')} | {it.get('decision_reason')}"
            )
        msg = "\n".join(lines_out) if lines_out else "(leer)"
        api.send_message(chat_id, msg[:3500])
        return

    if cmd == "/exec_show":
        try:
            eid = str(uuid.UUID(arg.split()[0].strip()))
        except (ValueError, IndexError):
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd, "arg": arg[:120]},
            )
            api.send_message(chat_id, "Usage: /exec_show <execution_uuid>")
            return
        status, data = lb.get_execution_telegram_summary(eid)
        if status != 200:
            op.log_action(
                outcome="rejected_http_error",
                chat_id=chat_id,
                user_id=user_id,
                execution_id=eid,
                http_status=status or None,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, f"Upstream-Fehler telegram-summary http={status}")
            return
        api.send_message(chat_id, _fmt_summary_block(data)[:3500])
        return

    if cmd == "/release_step1":
        try:
            eid = str(uuid.UUID(arg.split()[0].strip()))
        except (ValueError, IndexError):
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd, "arg": arg[:120]},
            )
            api.send_message(chat_id, "Usage: /release_step1 <execution_uuid>")
            return
        status, data = lb.get_execution_telegram_summary(eid)
        if status != 200:
            op.log_action(
                outcome="rejected_http_error",
                chat_id=chat_id,
                user_id=user_id,
                execution_id=eid,
                http_status=status or None,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, f"Upstream-Fehler http={status}")
            return
        if not data.get("eligible"):
            op.log_action(
                outcome="rejected_not_eligible",
                chat_id=chat_id,
                user_id=user_id,
                execution_id=eid,
                details={"cmd": cmd, "reason": data.get("reason")},
            )
            api.send_message(
                chat_id,
                f"Freigabe nicht moeglich: {data.get('reason')}\n{_fmt_summary_block(data)[:2500]}",
            )
            return
        code = secrets.token_urlsafe(8)[:10]
        h = _hash_code(code)
        pid = op.insert_pending(
            chat_id=chat_id,
            user_id=user_id,
            action_kind="operator_release",
            execution_id=eid,
            request_body_json={"execution_id": eid},
            summary_redacted=_fmt_summary_block(data),
            confirm_code_hash=h,
            ttl_sec=settings.telegram_operator_confirm_ttl_sec,
        )
        op.log_action(
            outcome="pending_created",
            chat_id=chat_id,
            user_id=user_id,
            action_kind="operator_release",
            execution_id=eid,
            pending_id=str(pid),
            details={"ttl_sec": settings.telegram_operator_confirm_ttl_sec},
        )
        api.send_message(
            chat_id,
            "Zweistufige Freigabe operator_release\n"
            f"{_fmt_summary_block(data)[:2000]}\n\n"
            f"pending_id={pid}\n"
            "Bestaetigung innerhalb TTL mit exakt:\n"
            f"/release_confirm {pid} {code}\n"
            f"/release_abort {pid} zum Abbrechen",
        )
        return

    if cmd == "/release_abort":
        try:
            pid = str(uuid.UUID(arg.split()[0].strip()))
        except (ValueError, IndexError):
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Usage: /release_abort <pending_uuid>")
            return
        row = op.get_open_pending(pid)
        if row is None:
            api.send_message(chat_id, "Pending unbekannt oder bereits abgeschlossen.")
            return
        if int(row["chat_id"]) != int(chat_id):
            op.log_action(
                outcome="rejected_wrong_chat",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Dieses Pending gehoert zu einem anderen Chat.")
            return
        op.mark_consumed(pid)
        op.log_action(
            outcome="pending_cancelled",
            chat_id=chat_id,
            user_id=user_id,
            pending_id=pid,
            details={"cmd": cmd},
        )
        api.send_message(chat_id, "Pending abgebrochen.")
        return

    if cmd == "/release_confirm":
        parts = arg.split()
        if len(parts) < 2:
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd},
            )
            api.send_message(
                chat_id,
                "Usage: /release_confirm <pending_uuid> <code> [<manual_action_token>]\n"
                "Drittes Feld erforderlich wenn TELEGRAM_OPERATOR_CONFIRM_TOKEN gesetzt ist.",
            )
            return
        try:
            pid = str(uuid.UUID(parts[0].strip()))
        except ValueError:
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "pending_uuid ungueltig.")
            return
        code = parts[1].strip()
        row = op.get_open_pending(pid)
        if row is None:
            op.log_action(
                outcome="rejected_expired",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd, "hint": "missing_or_consumed"},
            )
            api.send_message(chat_id, "Pending unbekannt, abgelaufen oder verbraucht.")
            return
        if int(row["chat_id"]) != int(chat_id):
            op.log_action(
                outcome="rejected_wrong_chat",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Falscher Chat fuer dieses Pending.")
            return
        exp = row.get("expires_at")
        if exp is not None:
            now = datetime.now(tz=UTC)
            if hasattr(exp, "tzinfo") and exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp < now:
                op.mark_consumed(pid)
                op.log_action(
                    outcome="rejected_expired",
                    chat_id=chat_id,
                    user_id=user_id,
                    pending_id=pid,
                    details={"cmd": cmd},
                )
                api.send_message(chat_id, "Pending abgelaufen.")
                return
        if _hash_code(code) != str(row.get("confirm_code_hash") or ""):
            op.log_action(
                outcome="rejected_bad_code",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Bestaetigungscode falsch.")
            return
        mt_ok, mt_fp = manual_confirm_token_verify(
            configured_token=settings.telegram_operator_confirm_token,
            parts=parts,
        )
        if not mt_ok:
            op.log_action(
                outcome="rejected_manual_token",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd, "hint": "missing_or_bad_manual_token"},
            )
            api.send_message(
                chat_id,
                "Manual-Action-Token fehlt oder falsch (TELEGRAM_OPERATOR_CONFIRM_TOKEN).",
            )
            return
        eid = row.get("execution_id")
        if not eid:
            api.send_message(chat_id, "Interner Fehler: execution_id fehlt.")
            return
        eid_str = str(eid)
        op.mark_consumed(pid)
        audit = {
            "telegram_chat_id": chat_id,
            "telegram_user_id": user_id,
            "telegram_pending_id": pid,
            "confirm_channel": "telegram",
            "rbac_scope": rbac_scope,
            "manual_action_token_fp": mt_fp,
        }
        st, resp = lb.post_operator_release(eid_str, audit=audit)
        if st == 200 and (isinstance(resp, dict) and resp.get("ok") is not False):
            op.log_action(
                outcome="executed_ok",
                chat_id=chat_id,
                user_id=user_id,
                action_kind="operator_release",
                execution_id=eid_str,
                pending_id=pid,
                http_status=st,
                details={"response_ok": True},
                rbac_scope=rbac_scope,
                manual_action_token_fp=mt_fp,
            )
            api.send_message(
                chat_id,
                f"operator_release ausgefuehrt execution_id={eid_str} http={st}",
            )
        else:
            op.log_action(
                outcome="executed_error",
                chat_id=chat_id,
                user_id=user_id,
                action_kind="operator_release",
                execution_id=eid_str,
                pending_id=pid,
                http_status=st or None,
                details={"response": json.dumps(resp)[:1800]},
                rbac_scope=rbac_scope,
                manual_action_token_fp=mt_fp,
            )
            api.send_message(
                chat_id,
                f"operator_release fehlgeschlagen http={st} detail={str(resp)[:1500]}",
            )
        return

    if cmd == "/emerg_step1":
        try:
            oid = str(uuid.UUID(arg.split()[0].strip()))
        except (ValueError, IndexError):
            op.log_action(
                outcome="rejected_invalid_args",
                chat_id=chat_id,
                user_id=user_id,
                details={"cmd": cmd},
            )
            api.send_message(
                chat_id,
                "Usage: /emerg_step1 <internal_order_uuid>\n"
                "Nur bestehende lokale Order-ID (kein freies Wunsch-Symbol).",
            )
            return
        body = {
            "source_service": "manual",
            "internal_order_id": oid,
            "reason": "telegram_operator_emergency",
            "note": "",
        }
        code = secrets.token_urlsafe(8)[:10]
        h = _hash_code(code)
        pid = op.insert_pending(
            chat_id=chat_id,
            user_id=user_id,
            action_kind="emergency_flatten",
            execution_id=None,
            request_body_json=body,
            summary_redacted=f"emergency_flatten internal_order_id={oid}",
            confirm_code_hash=h,
            ttl_sec=min(settings.telegram_operator_confirm_ttl_sec, 600),
        )
        op.log_action(
            outcome="pending_created",
            chat_id=chat_id,
            user_id=user_id,
            action_kind="emergency_flatten",
            pending_id=str(pid),
            details={"internal_order_id": oid},
        )
        api.send_message(
            chat_id,
            "NOTFALL: Emergency-Flatten (reduce-only Pfad live-broker)\n"
            f"internal_order_id={oid}\n"
            f"pending_id={pid}\n"
            f"/emerg_confirm {pid} {code}\n"
            f"/emerg_abort {pid}",
        )
        return

    if cmd == "/emerg_abort":
        try:
            pid = str(uuid.UUID(arg.split()[0].strip()))
        except (ValueError, IndexError):
            api.send_message(chat_id, "Usage: /emerg_abort <pending_uuid>")
            return
        row = op.get_open_pending(pid)
        if row is None:
            api.send_message(chat_id, "Pending unbekannt oder bereits abgeschlossen.")
            return
        if int(row["chat_id"]) != int(chat_id):
            op.log_action(
                outcome="rejected_wrong_chat",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Falscher Chat.")
            return
        op.mark_consumed(pid)
        op.log_action(
            outcome="pending_cancelled",
            chat_id=chat_id,
            user_id=user_id,
            pending_id=pid,
            details={"cmd": cmd, "action_kind": "emergency_flatten"},
        )
        api.send_message(chat_id, "Emergency-Pending abgebrochen.")
        return

    if cmd == "/emerg_confirm":
        parts = arg.split()
        if len(parts) < 2:
            api.send_message(
                chat_id,
                "Usage: /emerg_confirm <pending_uuid> <code> [<manual_action_token>]",
            )
            return
        try:
            pid = str(uuid.UUID(parts[0].strip()))
        except ValueError:
            api.send_message(chat_id, "pending_uuid ungueltig.")
            return
        code = parts[1].strip()
        row = op.get_open_pending(pid)
        if row is None:
            op.log_action(
                outcome="rejected_expired",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": "emerg_confirm"},
            )
            api.send_message(chat_id, "Pending unbekannt oder abgelaufen.")
            return
        if int(row["chat_id"]) != int(chat_id):
            op.log_action(
                outcome="rejected_wrong_chat",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Falscher Chat.")
            return
        exp = row.get("expires_at")
        if exp is not None:
            now = datetime.now(tz=UTC)
            if hasattr(exp, "tzinfo") and exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp < now:
                op.mark_consumed(pid)
                op.log_action(
                    outcome="rejected_expired",
                    chat_id=chat_id,
                    user_id=user_id,
                    pending_id=pid,
                    details={"cmd": cmd},
                )
                api.send_message(chat_id, "Abgelaufen.")
                return
        if _hash_code(code) != str(row.get("confirm_code_hash") or ""):
            op.log_action(
                outcome="rejected_bad_code",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd},
            )
            api.send_message(chat_id, "Code falsch.")
            return
        mt_ok, mt_fp = manual_confirm_token_verify(
            configured_token=settings.telegram_operator_confirm_token,
            parts=parts,
        )
        if not mt_ok:
            op.log_action(
                outcome="rejected_manual_token",
                chat_id=chat_id,
                user_id=user_id,
                pending_id=pid,
                details={"cmd": cmd, "hint": "missing_or_bad_manual_token"},
            )
            api.send_message(
                chat_id,
                "Manual-Action-Token fehlt oder falsch (TELEGRAM_OPERATOR_CONFIRM_TOKEN).",
            )
            return
        req = row.get("request_body_json")
        if not isinstance(req, dict):
            req = {}
        req = dict(req)
        req["note"] = f"telegram_pending={pid}"
        op.mark_consumed(pid)
        st, resp = lb.post_emergency_flatten(req)
        ok = st == 200 and isinstance(resp, dict) and resp.get("ok") is not False
        if ok:
            op.log_action(
                outcome="executed_ok",
                chat_id=chat_id,
                user_id=user_id,
                action_kind="emergency_flatten",
                pending_id=pid,
                http_status=st,
                details={"internal_order_id": str(req.get("internal_order_id"))},
                rbac_scope=rbac_scope,
                manual_action_token_fp=mt_fp,
            )
            api.send_message(chat_id, f"Emergency-Flatten angefordert http={st}")
        else:
            op.log_action(
                outcome="executed_error",
                chat_id=chat_id,
                user_id=user_id,
                action_kind="emergency_flatten",
                pending_id=pid,
                http_status=st or None,
                details={"response": json.dumps(resp)[:1800]},
                rbac_scope=rbac_scope,
                manual_action_token_fp=mt_fp,
            )
            api.send_message(
                chat_id,
                f"Emergency-Flatten fehlgeschlagen http={st} detail={str(resp)[:1500]}",
            )
        return

    api.send_message(chat_id, "Interner Dispatch-Fehler (Operator).")
