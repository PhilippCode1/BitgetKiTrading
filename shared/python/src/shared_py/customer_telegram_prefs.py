"""Persistierte Telegram-Benachrichtigungs-Präferenzen pro Tenant (613, 622)."""

from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.types.json import Json


DEFAULT_PREFS: dict[str, Any] = {
    "notify_orders_demo": True,
    "notify_orders_live": True,
    "notify_billing": True,
    "notify_contract": True,
    "notify_risk": True,
    "notify_ai_tip": False,
    "notify_signal_high_leverage": True,
    "signal_type_prefs_json": {},
}

_PREF_BOOL_KEYS = frozenset(
    {
        "notify_orders_demo",
        "notify_orders_live",
        "notify_billing",
        "notify_contract",
        "notify_risk",
        "notify_ai_tip",
        "notify_signal_high_leverage",
    }
)

# Bot /get-prefs: nur skalare Schalter; JSON-Map (Signaltypen) nur im Web/API.
NOTIFY_PREFS_ORDERED_BOOL_KEYS: tuple[str, ...] = tuple(
    sorted(_PREF_BOOL_KEYS)
)


def _parse_signal_type_prefs(raw: object) -> dict[str, bool]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    elif isinstance(raw, dict):
        obj = raw
    else:
        return {}
    out: dict[str, bool] = {}
    for k, v in obj.items():
        if k is not None:
            out[str(k).strip().upper()] = bool(v)
    return out


def fetch_notify_prefs_merged(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any]:
    """
    Liest Zeile oder liefert DEFAULT_PREFS (keine Zeile = Defaults).
    Fuer Signaltyp-Map: ``signal_type_prefs_json`` — dict.
    """
    try:
        row = conn.execute(
            """
            SELECT notify_orders_demo, notify_orders_live, notify_billing,
                   notify_contract, notify_risk, notify_ai_tip,
                   notify_signal_high_leverage, signal_type_prefs_json
            FROM app.customer_telegram_notify_prefs
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()
    except (pg_errors.UndefinedTable, pg_errors.UndefinedColumn):
        return {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_PREFS.items()}
    if row is None:
        d = {k: v for k, v in DEFAULT_PREFS.items()}
    else:
        rowd = dict(row)
        d = {k: DEFAULT_PREFS[k] for k in DEFAULT_PREFS}
        d["notify_orders_demo"] = bool(rowd.get("notify_orders_demo", True))
        d["notify_orders_live"] = bool(rowd.get("notify_orders_live", True))
        d["notify_billing"] = bool(rowd.get("notify_billing", True))
        d["notify_contract"] = bool(rowd.get("notify_contract", True))
        d["notify_risk"] = bool(rowd.get("notify_risk", True))
        d["notify_ai_tip"] = bool(rowd.get("notify_ai_tip", False))
        d["notify_signal_high_leverage"] = bool(
            rowd.get("notify_signal_high_leverage", True)
        )
        d["signal_type_prefs_json"] = _parse_signal_type_prefs(
            rowd.get("signal_type_prefs_json", {})
        )
    return d


def upsert_notify_prefs(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    notify_orders_demo: bool | None = None,
    notify_orders_live: bool | None = None,
    notify_billing: bool | None = None,
    notify_contract: bool | None = None,
    notify_risk: bool | None = None,
    notify_ai_tip: bool | None = None,
    notify_signal_high_leverage: bool | None = None,
    signal_type_prefs_json: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Schreibt nur übergebene Felder; übrige bleiben aus bestehender Zeile oder Default."""
    cur = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
    for k in _PREF_BOOL_KEYS:
        v = locals().get(k)
        if v is not None:
            cur[k] = bool(v)
    if signal_type_prefs_json is not None:
        merged = _parse_signal_type_prefs(cur.get("signal_type_prefs_json", {}))
        for kt, val in signal_type_prefs_json.items():
            merged[str(kt).strip().upper()] = bool(val)
        cur["signal_type_prefs_json"] = merged
    st_json = Json(cur.get("signal_type_prefs_json") or {})
    try:
        conn.execute(
            """
            INSERT INTO app.customer_telegram_notify_prefs (
                tenant_id, notify_orders_demo, notify_orders_live, notify_billing,
                notify_contract, notify_risk, notify_ai_tip,
                notify_signal_high_leverage, signal_type_prefs_json, updated_ts
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                notify_orders_demo = EXCLUDED.notify_orders_demo,
                notify_orders_live = EXCLUDED.notify_orders_live,
                notify_billing = EXCLUDED.notify_billing,
                notify_contract = EXCLUDED.notify_contract,
                notify_risk = EXCLUDED.notify_risk,
                notify_ai_tip = EXCLUDED.notify_ai_tip,
                notify_signal_high_leverage = EXCLUDED.notify_signal_high_leverage,
                signal_type_prefs_json = EXCLUDED.signal_type_prefs_json,
                updated_ts = now()
            """,
            (
                tenant_id,
                cur["notify_orders_demo"],
                cur["notify_orders_live"],
                cur["notify_billing"],
                cur["notify_contract"],
                cur["notify_risk"],
                cur["notify_ai_tip"],
                cur["notify_signal_high_leverage"],
                st_json,
            ),
        )
    except (pg_errors.UndefinedTable, pg_errors.UndefinedColumn):
        conn.execute(
            """
            INSERT INTO app.customer_telegram_notify_prefs (
                tenant_id, notify_orders_demo, notify_orders_live, notify_billing,
                notify_contract, notify_risk, notify_ai_tip, updated_ts
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                notify_orders_demo = EXCLUDED.notify_orders_demo,
                notify_orders_live = EXCLUDED.notify_orders_live,
                notify_billing = EXCLUDED.notify_billing,
                notify_contract = EXCLUDED.notify_contract,
                notify_risk = EXCLUDED.notify_risk,
                notify_ai_tip = EXCLUDED.notify_ai_tip,
                updated_ts = now()
            """,
            (
                tenant_id,
                cur["notify_orders_demo"],
                cur["notify_orders_live"],
                cur["notify_billing"],
                cur["notify_contract"],
                cur["notify_risk"],
                cur["notify_ai_tip"],
            ),
        )
    return cur


def audit_prefs_changed(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    detail: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'telegram_notify_prefs_updated', %s, %s::jsonb)
        """,
        (tenant_id, actor[:200], Json(detail)),
    )
