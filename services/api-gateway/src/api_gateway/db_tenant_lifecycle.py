"""
Postgres: Prompt-11-Kundenlebenszyklus, Audit und Sync nach tenant_modul_mate_gates.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.types.json import Json
from shared_py.customer_lifecycle import (
    CustomerLifecycleStatus,
    TransitionActor,
    customer_commercial_gates_for_prompt11,
    derive_capabilities_from_prompt11,
    is_prompt11_transition_allowed,
    prompt11_journey_title_de,
    trial_duration_days,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_tenant_lifecycle_row(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, lifecycle_status, email_verified,
               trial_started_at, trial_ends_at, status_before_suspension,
               cancelled_ts, updated_ts
        FROM app.tenant_customer_lifecycle
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    return dict(row) if row else None


def _trial_clock_active(row: dict[str, Any], *, now: datetime) -> bool:
    st = str(row.get("lifecycle_status") or "")
    if st != CustomerLifecycleStatus.TRIAL_ACTIVE.value:
        return False
    te = row.get("trial_ends_at")
    if te is None:
        return False
    if isinstance(te, str):
        te = datetime.fromisoformat(te.replace("Z", "+00:00"))
    return now <= te


def apply_trial_expiry_if_due(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str = "system",
) -> bool:
    """
    Lazy Uebergang trial_active -> trial_expired wenn trial_ends_at ueberschritten.
    Returns True wenn eine Aenderung stattfand.
    """
    row = fetch_tenant_lifecycle_row(conn, tenant_id=tenant_id)
    if row is None:
        return False
    st = str(row.get("lifecycle_status") or "")
    if st != CustomerLifecycleStatus.TRIAL_ACTIVE.value:
        return False
    te = row.get("trial_ends_at")
    if te is None:
        return False
    if isinstance(te, str):
        te = datetime.fromisoformat(te.replace("Z", "+00:00"))
    now = _utc_now()
    if now <= te:
        return False
    from_s = CustomerLifecycleStatus.TRIAL_ACTIVE
    to_s = CustomerLifecycleStatus.TRIAL_EXPIRED
    with conn.transaction():
        conn.execute(
            """
            UPDATE app.tenant_customer_lifecycle
            SET lifecycle_status = %s, updated_ts = now()
            WHERE tenant_id = %s AND lifecycle_status = %s
            """,
            (to_s.value, tenant_id, from_s.value),
        )
        insert_lifecycle_audit(
            conn,
            tenant_id=tenant_id,
            from_status=from_s.value,
            to_status=to_s.value,
            actor=actor,
            actor_role=TransitionActor.SYSTEM.value,
            reason_code="trial_period_elapsed",
            meta_json={"trial_ends_at": te.isoformat().replace("+00:00", "Z")},
        )
        gates = customer_commercial_gates_for_prompt11(
            to_s,
            trial_clock_active=False,
        )
        upsert_modul_mate_gates(conn, tenant_id=tenant_id, gates=gates)
    return True


def insert_lifecycle_audit(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    from_status: str | None,
    to_status: str,
    actor: str,
    actor_role: str,
    reason_code: str | None,
    meta_json: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.tenant_lifecycle_audit (
            tenant_id, from_status, to_status, actor, actor_role, reason_code, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            tenant_id,
            from_status,
            to_status,
            actor[:500],
            actor_role[:64],
            reason_code[:128] if reason_code else None,
            Json(meta_json),
        ),
    )


def upsert_modul_mate_gates(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    gates: Any,
) -> None:
    d = asdict(gates)
    conn.execute(
        """
        INSERT INTO app.tenant_modul_mate_gates (
            tenant_id, trial_active, contract_accepted, admin_live_trading_granted,
            subscription_active, account_paused, account_suspended, updated_ts
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            trial_active = EXCLUDED.trial_active,
            contract_accepted = EXCLUDED.contract_accepted,
            admin_live_trading_granted = EXCLUDED.admin_live_trading_granted,
            subscription_active = EXCLUDED.subscription_active,
            account_paused = EXCLUDED.account_paused,
            account_suspended = EXCLUDED.account_suspended,
            updated_ts = now()
        """,
        (
            tenant_id,
            d["trial_active"],
            d["contract_accepted"],
            d["admin_live_trading_granted"],
            d["subscription_active"],
            d["account_paused"],
            d["account_suspended"],
        ),
    )


def transition_lifecycle(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    to_status: CustomerLifecycleStatus,
    actor: str,
    actor_role: TransitionActor,
    reason_code: str | None = None,
    meta_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wirft ValueError bei unerlaubtem Wechsel oder Vorbedingungen."""
    meta_json = meta_json or {}
    apply_trial_expiry_if_due(conn, tenant_id=tenant_id, actor="system")
    row = fetch_tenant_lifecycle_row(conn, tenant_id=tenant_id)
    if row is None:
        raise ValueError("lifecycle_row_missing")

    from_status = CustomerLifecycleStatus(str(row["lifecycle_status"]))
    suspended_prev: CustomerLifecycleStatus | None = None
    raw_prev = row.get("status_before_suspension")
    if raw_prev:
        suspended_prev = CustomerLifecycleStatus(str(raw_prev))

    if not is_prompt11_transition_allowed(
        from_status,
        to_status,
        actor_role,
        suspended_previous=suspended_prev,
    ):
        raise ValueError("transition_not_allowed")

    now = _utc_now()

    trial_started = row.get("trial_started_at")
    trial_ends = row.get("trial_ends_at")
    if to_status == CustomerLifecycleStatus.TRIAL_ACTIVE:
        if from_status != CustomerLifecycleStatus.REGISTERED:
            raise ValueError("start_trial_requires_registered")
        if not bool(row.get("email_verified")):
            raise ValueError("start_trial_requires_email_verified")
        trial_started = now
        trial_ends = now + timedelta(days=trial_duration_days())

    prev_sb: str | None = row.get("status_before_suspension")
    new_sb = prev_sb
    if to_status == CustomerLifecycleStatus.SUSPENDED:
        new_sb = from_status.value
    elif from_status == CustomerLifecycleStatus.SUSPENDED:
        new_sb = None

    cancelled_ts = row.get("cancelled_ts")
    if to_status == CustomerLifecycleStatus.CANCELLED:
        cancelled_ts = now

    with conn.transaction():
        conn.execute(
            """
            UPDATE app.tenant_customer_lifecycle
            SET lifecycle_status = %s,
                trial_started_at = %s,
                trial_ends_at = %s,
                status_before_suspension = %s,
                cancelled_ts = %s,
                updated_ts = now()
            WHERE tenant_id = %s
            """,
            (
                to_status.value,
                trial_started,
                trial_ends,
                new_sb,
                cancelled_ts,
                tenant_id,
            ),
        )
        insert_lifecycle_audit(
            conn,
            tenant_id=tenant_id,
            from_status=from_status.value,
            to_status=to_status.value,
            actor=actor,
            actor_role=actor_role.value,
            reason_code=reason_code,
            meta_json=meta_json,
        )
        refreshed = fetch_tenant_lifecycle_row(conn, tenant_id=tenant_id)
        assert refreshed is not None
        st = CustomerLifecycleStatus(str(refreshed["lifecycle_status"]))
        tc = _trial_clock_active(refreshed, now=_utc_now())
        gates = customer_commercial_gates_for_prompt11(st, trial_clock_active=tc)
        upsert_modul_mate_gates(conn, tenant_id=tenant_id, gates=gates)

    out = fetch_tenant_lifecycle_row(conn, tenant_id=tenant_id)
    assert out is not None
    return out


def fetch_lifecycle_audit_recent(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    limit: int = 40,
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT audit_id, from_status, to_status, actor, actor_role, reason_code,
               meta_json, created_ts
        FROM app.tenant_lifecycle_audit
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ct = d.get("created_ts")
        d["created_ts"] = ct.isoformat() if ct is not None else None
        out.append(d)
    return out


def build_lifecycle_public_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Oeffentliche Antwort fuer Kunden-API (keine internen Admin-Felder)."""
    st = CustomerLifecycleStatus(str(row["lifecycle_status"]))
    now = _utc_now()
    tc = _trial_clock_active(row, now=now)
    caps = derive_capabilities_from_prompt11(
        st,
        email_verified=bool(row.get("email_verified")),
        trial_clock_active=tc,
    )
    cap_d = asdict(caps)
    trial_started = row.get("trial_started_at")
    trial_ends = row.get("trial_ends_at")
    return {
        "schema_version": "tenant-lifecycle-v1",
        "status": st.value,
        "title_de": prompt11_journey_title_de(st),
        "email_verified": bool(row.get("email_verified")),
        "trial": {
            "duration_days": trial_duration_days(),
            "started_at": trial_started.isoformat() if trial_started else None,
            "ends_at": trial_ends.isoformat() if trial_ends else None,
            "clock_active": tc,
        },
        "capabilities": cap_d,
        "gates_preview": asdict(
            customer_commercial_gates_for_prompt11(st, trial_clock_active=tc)
        ),
    }


def set_email_verified(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    verified: bool = True,
) -> None:
    row = fetch_tenant_lifecycle_row(conn, tenant_id=tenant_id)
    if row is None:
        raise ValueError("lifecycle_row_missing")
    cur = str(row["lifecycle_status"])
    with conn.transaction():
        conn.execute(
            """
            UPDATE app.tenant_customer_lifecycle
            SET email_verified = %s, updated_ts = now()
            WHERE tenant_id = %s
            """,
            (verified, tenant_id),
        )
        insert_lifecycle_audit(
            conn,
            tenant_id=tenant_id,
            from_status=cur,
            to_status=cur,
            actor=actor,
            actor_role=TransitionActor.SYSTEM.value,
            reason_code=(
                "email_verification" if verified else "email_verification_revoked"
            ),
            meta_json={"verified": verified},
        )
