from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from shared_py.observability.execution_forensic import (
    build_forensic_timeline_phases,
    build_live_broker_forensic_snapshot,
    redact_nested_mapping,
)


def _j(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _i(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ts_ms_to_iso(value: Any) -> str | None:
    iv = _i(value)
    if iv is None:
        return None
    return datetime.fromtimestamp(iv / 1000.0, tz=timezone.utc).isoformat()


def _serialize_cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, memoryview)):
        return None
    return v


def _row_public(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize_cell(v) for k, v in row.items()}


def _runtime_instrument_metadata(raw: Any) -> dict[str, Any] | None:
    meta = _j(raw)
    if not isinstance(meta, dict):
        return None
    entry = meta.get("entry")
    if isinstance(entry, dict):
        out = dict(entry)
        if meta.get("snapshot_id") not in (None, ""):
            out.setdefault("snapshot_id", str(meta.get("snapshot_id")))
        if isinstance(meta.get("session_state"), dict):
            out["session_state"] = dict(meta.get("session_state"))
        if isinstance(meta.get("health_status"), str):
            out["health_status"] = meta.get("health_status")
        if isinstance(meta.get("health_reasons"), list):
            out["health_reasons"] = list(meta.get("health_reasons"))
        return out
    return meta


def _shadow_live_fields(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("shadow_live_divergence")
    if not isinstance(raw, dict):
        out: dict[str, Any] = {
            "shadow_live_match_ok": None,
            "shadow_live_hard_violations": None,
            "shadow_live_soft_violations": None,
        }
    else:
        out = {
            "shadow_live_match_ok": raw.get("match_ok"),
            "shadow_live_hard_violations": raw.get("hard_violations"),
            "shadow_live_soft_violations": raw.get("soft_violations"),
        }
    sml = payload.get("shadow_match_latch")
    if isinstance(sml, dict):
        out["shadow_match_latch_ok"] = sml.get("ok")
        out["shadow_match_latch_skipped"] = sml.get("skipped")
        out["shadow_match_latch_waited_ms"] = sml.get("waited_ms")
        out["shadow_match_latch_error"] = sml.get("error")
    else:
        out["shadow_match_latch_ok"] = None
        out["shadow_match_latch_skipped"] = None
        out["shadow_match_latch_waited_ms"] = None
        out["shadow_match_latch_error"] = None
    return out


def bitget_private_status_from_reconcile_details(details: Any) -> dict[str, Any]:
    """
    Kompakte, UI-taugliche Bitget-Privatdiagnose aus live.reconcile_snapshots.details_json.
    Keine Secrets; entspricht exchange_probe aus dem live-broker Reconcile-Lauf.
    """
    unknown: dict[str, Any] = {
        "ui_status": "unknown",
        "bitget_connection_label": "unknown",
        "credential_profile": None,
        "demo_mode": None,
        "public_api_ok": None,
        "private_api_configured": None,
        "private_auth_ok": None,
        "private_detail_de": None,
        "private_auth_detail_de": None,
        "private_auth_classification": None,
        "private_auth_exchange_code": None,
        "paptrading_header_active": None,
        "credential_isolation_relaxed": None,
        "bitget_private_rest": None,
    }
    if not isinstance(details, dict):
        return unknown
    ep = details.get("exchange_probe")
    if not isinstance(ep, dict):
        return unknown
    demo = ep.get("demo_mode")
    auth_ok = ep.get("private_auth_ok")
    keys_ok = ep.get("private_api_configured")
    pub_ok = ep.get("public_api_ok")
    if auth_ok is True:
        ui_status = "private_ok"
    elif keys_ok is True and auth_ok is False:
        ui_status = "credentials_invalid"
    elif keys_ok is False:
        ui_status = "credentials_missing"
    elif pub_ok is False:
        ui_status = "exchange_unreachable"
    else:
        ui_status = "unknown"
    if keys_ok is None and pub_ok is None:
        conn_lbl = "inactive"
    else:
        conn_lbl = "demo" if demo is True else "live"
    cred_profile = ep.get("credential_profile")
    if not isinstance(cred_profile, str) or not cred_profile.strip():
        cred_profile = "demo" if demo is True else ("live" if demo is False else None)
    bpr = ep.get("bitget_private_rest")
    if not isinstance(bpr, dict):
        bpr = None
    return {
        "ui_status": ui_status,
        "bitget_connection_label": conn_lbl,
        "credential_profile": cred_profile,
        "demo_mode": demo,
        "public_api_ok": pub_ok,
        "private_api_configured": keys_ok,
        "private_auth_ok": auth_ok,
        "private_detail_de": ep.get("private_detail_de"),
        "private_auth_detail_de": ep.get("private_auth_detail_de"),
        "private_auth_classification": ep.get("private_auth_classification"),
        "private_auth_exchange_code": ep.get("private_auth_exchange_code"),
        "paptrading_header_active": ep.get("paptrading_header_active"),
        "credential_isolation_relaxed": ep.get("credential_isolation_relaxed"),
        "bitget_private_rest": bpr,
    }


def compute_operator_live_submission_summary(
    *,
    reconcile_status: str | None,
    upstream_ok: bool,
    execution_mode: str | None,
    live_trade_enable: bool,
    live_submission_enabled: bool,
    safety_latch_active: bool,
    active_kill_switches: list[dict[str, Any]],
    bitget_private_status: dict[str, Any],
    require_shadow_match_before_live: bool,
) -> dict[str, Any]:
    """
    Einheitliche Operator-Sicht: Live ist deaktiviert, bereit, blockiert (Safety/Exchange/Upstream)
    oder fehlerhaft (Reconcile) — mit konkreten deutschen Begruendungen (kein stilles „nichts passiert“).
    """
    ks_count = len(active_kill_switches)
    st_raw = (reconcile_status or "").strip()
    st = st_raw.lower()

    base_meta = {
        "safety_kill_switch_count": ks_count,
        "safety_latch_active": bool(safety_latch_active),
    }

    if not st_raw:
        return {
            "lane": "live_lane_unknown",
            "reasons_de": [
                "Kein Reconcile-Status im letzten Snapshot — Live-Broker-Reconcile und Datenbank pruefen."
            ],
            **base_meta,
        }

    if st != "ok":
        return {
            "lane": "live_lane_degraded_reconcile",
            "reasons_de": [
                f"Reconcile-Status ist nicht „ok“ (aktuell: „{reconcile_status}“). "
                "Live-Orders werden nicht als betriebssicher eingestuft, bis der Lauf wieder gruen ist."
            ],
            **base_meta,
        }

    if not upstream_ok:
        return {
            "lane": "live_lane_blocked_upstream",
            "reasons_de": [
                "Upstream-Signalpfad wird als nicht gesund gemeldet (upstream_ok=false). "
                "Ohne gesunden Eingang werden keine neuen Live-Intents zuverlaessig verarbeitet."
            ],
            **base_meta,
        }

    if ks_count > 0:
        lines: list[str] = []
        for row in active_kill_switches[:12]:
            r = row.get("reason") or "—"
            sc = row.get("scope") or "—"
            sk = row.get("scope_key") or "—"
            lines.append(f"Kill-Switch aktiv ({sc} / {sk}): {r}")
        return {
            "lane": "live_lane_blocked_safety",
            "reasons_de": lines,
            **base_meta,
        }

    if safety_latch_active:
        return {
            "lane": "live_lane_blocked_safety",
            "reasons_de": [
                "Safety-Latch ist aktiv (manueller oder automatisierter Stop). "
                "Riskante Aktionen bleiben blockiert, bis ein befugter Operator die Freigabe setzt "
                "(Audit-Kategorie safety_latch, ggf. POST safety-latch/release)."
            ],
            **{**base_meta, "safety_latch_active": True},
        }

    em = (execution_mode or "").strip().lower()
    if em == "paper":
        return {
            "lane": "live_lane_disabled_config",
            "reasons_de": [
                "System laeuft im Paper-Modus. Live-Order-Submission an die Boerse ist absichtlich nicht aktiv."
            ],
            **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
        }

    if em == "shadow" and (not live_trade_enable or not live_submission_enabled):
        reasons: list[str] = []
        if not live_trade_enable:
            reasons.append(
                "Shadow-Modus: Live-Gate (live_trade_enable) ist aus — keine Live-Intents."
            )
        if not live_submission_enabled:
            reasons.append(
                "Shadow-Modus: Boersen-Submission (live_submission_enabled) ist aus — typisch bis Live explizit freigeschaltet wird."
            )
        return {
            "lane": "live_lane_disabled_config",
            "reasons_de": reasons
            or ["Shadow-Modus: Live-Order-Submission ist derzeit nicht aktiv."],
            **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
        }

    if not live_trade_enable:
        reasons2: list[str] = [
            "Live-Gate (live_trade_enable) ist aus — die Strategie sendet keine Live-Intents."
        ]
        if not live_submission_enabled:
            reasons2.append(
                "Zusaetzlich: Order-Submission an die Boerse ist aus (live_submission_enabled)."
            )
        return {
            "lane": "live_lane_disabled_config",
            "reasons_de": reasons2,
            **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
        }

    if not live_submission_enabled:
        return {
            "lane": "live_lane_disabled_config",
            "reasons_de": [
                "Live-Gate ist an, aber Boersen-Submission ist aus (live_submission_enabled im Reconcile-Snapshot). "
                "Ursache oft Konfiguration oder vorheriger Safety-Pfad — Runtime-Details und Audit pruefen."
            ],
            **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
        }

    ui = (
        bitget_private_status.get("ui_status")
        if isinstance(bitget_private_status, dict)
        else None
    )
    if ui in ("credentials_invalid", "credentials_missing", "exchange_unreachable"):
        msgs = {
            "credentials_invalid": (
                "Bitget Privat-API: Anmeldung fehlgeschlagen (Schluessel vorhanden, aber abgelehnt). "
                "Live-Orders wuerden an der Exchange scheitern."
            ),
            "credentials_missing": (
                "Bitget Privat-API: Keine gueltigen API-Schluessel fuer den gewaehlten Profil-Pfad. "
                "Live-Submission ist nicht moeglich."
            ),
            "exchange_unreachable": (
                "Bitget-Erreichbarkeit (oeffentlich/Netz) ist problematisch. "
                "Vor Live-Handel Netzwerk und Provider pruefen."
            ),
        }
        return {
            "lane": "live_lane_blocked_exchange",
            "reasons_de": [msgs.get(str(ui), "Bitget-Status unguenstig fuer Live.")],
            **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
        }

    hints: list[str] = []
    if require_shadow_match_before_live:
        hints.append(
            "Hinweis: Shadow-Match vor Live ist aktiv — abweichende Shadow-/Live-Signale blockieren den Trade "
            "(Spalten Shadow-Live und decision_reason in Execution Decisions, ggf. shadow_live_divergence_gate)."
        )
    return {
        "lane": "live_lane_ready",
        "reasons_de": hints,
        **{**base_meta, "safety_kill_switch_count": 0, "safety_latch_active": False},
    }


def fetch_live_broker_runtime(conn: psycopg.Connection[Any]) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT *
        FROM live.reconcile_snapshots
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    details = _j(data.get("details_json")) or {}
    execution_controls: dict[str, Any] = {}
    if isinstance(details, dict):
        raw_execution_controls = details.get("execution_controls")
        if isinstance(raw_execution_controls, dict):
            execution_controls = raw_execution_controls
    order_rows = conn.execute(
        """
        SELECT status, count(*) AS total
        FROM live.orders
        GROUP BY status
        """
    ).fetchall()
    kill_switch_rows = conn.execute(
        """
        SELECT *
        FROM (
            SELECT DISTINCT ON (scope, scope_key) *
            FROM live.kill_switch_events
            WHERE event_type IN ('arm', 'release')
            ORDER BY scope, scope_key, created_ts DESC
        ) latest
        WHERE is_active = true
        ORDER BY created_ts DESC
        LIMIT 20
        """
    ).fetchall()
    latch_row = conn.execute(
        """
        SELECT action
        FROM live.audit_trails
        WHERE category = 'safety_latch'
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    safety_latch_active = False
    if latch_row is not None:
        safety_latch_active = str(dict(latch_row).get("action") or "") == "arm"
    catalog_row = conn.execute(
        """
        SELECT snapshot_id, status, refreshed_families_json, counts_json, capability_matrix_json,
               warnings_json, errors_json, fetch_completed_ts_ms
        FROM app.instrument_catalog_snapshots
        ORDER BY fetch_completed_ts_ms DESC NULLS LAST, fetch_started_ts_ms DESC
        LIMIT 1
        """
    ).fetchone()
    latest_metadata_row = conn.execute(
        """
        SELECT payload_json, trace_json
        FROM live.execution_decisions
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    instrument_catalog = None
    if catalog_row is not None:
        cat = dict(catalog_row)
        instrument_catalog = {
            "snapshot_id": str(cat["snapshot_id"]),
            "status": cat["status"],
            "refreshed_families": _j(cat.get("refreshed_families_json")) or [],
            "counts": _j(cat.get("counts_json")) or {},
            "capability_matrix": _j(cat.get("capability_matrix_json")) or [],
            "warnings": _j(cat.get("warnings_json")) or [],
            "errors": _j(cat.get("errors_json")) or [],
            "fetch_completed_ts_ms": _i(cat.get("fetch_completed_ts_ms")),
        }
    current_instrument_metadata = None
    if latest_metadata_row is not None:
        md = dict(latest_metadata_row)
        payload = _j(md.get("payload_json")) or {}
        trace = _j(md.get("trace_json")) or {}
        current_instrument_metadata = _runtime_instrument_metadata(
            payload.get("instrument_metadata") or trace.get("instrument_metadata")
        )
    bitget_private_status = bitget_private_status_from_reconcile_details(details)
    active_kill_switches: list[dict[str, Any]] = [
        {
            "kill_switch_event_id": str(row["kill_switch_event_id"]),
            "scope": row["scope"],
            "scope_key": row["scope_key"],
            "event_type": row["event_type"],
            "reason": row["reason"],
            "source": row["source"],
            "symbol": row.get("symbol"),
            "created_ts": row["created_ts"].isoformat()
            if row.get("created_ts")
            else None,
        }
        for row in kill_switch_rows
    ]
    req_shadow = bool(execution_controls.get("require_shadow_match_before_live"))
    sm_to = execution_controls.get("shadow_match_latch_timeout_ms")
    sm_ttl = execution_controls.get("shadow_match_redis_ttl_sec")
    live_te = bool(execution_controls.get("live_trade_enable"))
    live_sub = bool(data["live_submission_enabled"])
    operator_live_submission = compute_operator_live_submission_summary(
        reconcile_status=str(data.get("status") or ""),
        upstream_ok=bool(data["upstream_ok"]),
        execution_mode=str(data.get("runtime_mode") or ""),
        live_trade_enable=live_te,
        live_submission_enabled=live_sub,
        safety_latch_active=safety_latch_active,
        active_kill_switches=active_kill_switches,
        bitget_private_status=bitget_private_status,
        require_shadow_match_before_live=req_shadow,
    )
    return {
        "reconcile_snapshot_id": str(data["reconcile_snapshot_id"]),
        "status": data["status"],
        "execution_mode": data["runtime_mode"],
        "runtime_mode": data["runtime_mode"],
        "strategy_execution_mode": execution_controls.get("strategy_execution_mode"),
        "upstream_ok": bool(data["upstream_ok"]),
        "paper_path_active": bool(execution_controls.get("paper_path_active")),
        "shadow_trade_enable": bool(execution_controls.get("shadow_trade_enable")),
        "shadow_enabled": bool(data["shadow_enabled"]),
        "shadow_path_active": bool(data["shadow_enabled"]),
        "live_trade_enable": live_te,
        "live_submission_enabled": live_sub,
        "live_order_submission_enabled": live_sub,
        "require_shadow_match_before_live": req_shadow,
        "shadow_match_latch_timeout_ms": int(sm_to) if sm_to is not None else 500,
        "shadow_match_redis_ttl_sec": int(sm_ttl) if sm_ttl is not None else 300,
        "decision_counts": _j(data.get("decision_counts_json")) or {},
        "details": details,
        "order_status_counts": {
            str(row["status"]): int(row["total"]) for row in order_rows
        },
        "active_kill_switches": active_kill_switches,
        "safety_latch_active": safety_latch_active,
        "instrument_catalog": instrument_catalog,
        "current_instrument_metadata": current_instrument_metadata,
        "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
        "bitget_private_status": bitget_private_status,
        "operator_live_submission": operator_live_submission,
    }


def fetch_live_broker_decisions(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.*,
               rel.released_ts AS operator_release_ts,
               rel.source AS operator_release_source,
               rs.trade_action AS risk_trade_action,
               rs.decision_state AS risk_decision_state,
               rs.primary_reason AS risk_primary_reason,
               rs.reasons_json AS risk_reasons_json
        FROM live.execution_decisions d
        LEFT JOIN live.execution_operator_releases rel
          ON rel.execution_id = d.execution_id
        LEFT JOIN live.execution_risk_snapshots rs
          ON rs.execution_decision_id = d.execution_id
        ORDER BY d.created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        payload = _j(data.get("payload_json")) or {}
        signal_payload = payload.get("signal_payload") if isinstance(payload, dict) else {}
        if not isinstance(signal_payload, dict):
            signal_payload = {}
        slf = _shadow_live_fields(payload) if isinstance(payload, dict) else _shadow_live_fields({})
        sig_mf = (
            signal_payload.get("market_family")
            if isinstance(signal_payload.get("market_family"), str)
            else None
        )
        sig_pb = (
            signal_payload.get("playbook_id") if isinstance(signal_payload.get("playbook_id"), str) else None
        )
        sig_lane = (
            signal_payload.get("meta_trade_lane")
            if isinstance(signal_payload.get("meta_trade_lane"), str)
            else None
        )
        sig_cid = (
            signal_payload.get("canonical_instrument_id")
            if isinstance(signal_payload.get("canonical_instrument_id"), str)
            else None
        )
        mirror_eligible = None
        if isinstance(payload, dict):
            raw_me = payload.get("live_mirror_eligible")
            if isinstance(raw_me, bool):
                mirror_eligible = raw_me
            elif isinstance(raw_me, str):
                mirror_eligible = raw_me.lower() in ("true", "1", "yes")
        out.append(
            {
                "execution_id": str(data["execution_id"]),
                "source_service": data["source_service"],
                "source_signal_id": data.get("source_signal_id"),
                "symbol": data["symbol"],
                "timeframe": data.get("timeframe"),
                "direction": data["direction"],
                "signal_market_family": sig_mf,
                "signal_playbook_id": sig_pb,
                "signal_meta_trade_lane": sig_lane,
                "signal_canonical_instrument_id": sig_cid,
                "live_mirror_eligible": mirror_eligible,
                "requested_runtime_mode": data["requested_runtime_mode"],
                "effective_runtime_mode": data["effective_runtime_mode"],
                "decision_action": data["decision_action"],
                "decision_reason": data["decision_reason"],
                "order_type": data["order_type"],
                "leverage": _i(data.get("leverage")),
                "signal_allowed_leverage": _i(
                    payload.get("signal_allowed_leverage")
                    if payload.get("signal_allowed_leverage") is not None
                    else signal_payload.get("allowed_leverage")
                ),
                "signal_recommended_leverage": _i(
                    payload.get("signal_recommended_leverage")
                    if payload.get("signal_recommended_leverage") is not None
                    else signal_payload.get("recommended_leverage")
                ),
                "signal_trade_action": payload.get("signal_trade_action")
                if payload.get("signal_trade_action") is not None
                else signal_payload.get("trade_action"),
                "signal_leverage_policy_version": payload.get("signal_leverage_policy_version")
                if payload.get("signal_leverage_policy_version") is not None
                else signal_payload.get("leverage_policy_version"),
                "signal_leverage_cap_reasons_json": (
                    payload.get("signal_leverage_cap_reasons_json")
                    if payload.get("signal_leverage_cap_reasons_json") is not None
                    else signal_payload.get("leverage_cap_reasons_json")
                )
                or [],
                "approved_7x": bool(data["approved_7x"]),
                "qty_base": str(data["qty_base"]) if data.get("qty_base") is not None else None,
                "entry_price": (
                    str(data["entry_price"]) if data.get("entry_price") is not None else None
                ),
                "stop_loss": str(data["stop_loss"]) if data.get("stop_loss") is not None else None,
                "take_profit": (
                    str(data["take_profit"]) if data.get("take_profit") is not None else None
                ),
                "operator_release_exists": data.get("operator_release_ts") is not None,
                "operator_release_source": data.get("operator_release_source"),
                "operator_release_ts": data["operator_release_ts"].isoformat()
                if data.get("operator_release_ts")
                else None,
                "risk_trade_action": data.get("risk_trade_action"),
                "risk_decision_state": data.get("risk_decision_state"),
                "risk_primary_reason": data.get("risk_primary_reason"),
                "risk_reasons_json": _j(data.get("risk_reasons_json")) or [],
                **slf,
                "payload": payload,
                "trace": _j(data.get("trace_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
                "updated_ts": data["updated_ts"].isoformat() if data.get("updated_ts") else None,
            }
        )
    return out


def fetch_live_broker_paper_reference(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM live.paper_reference_events
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "reference_event_id": str(data["reference_event_id"]),
                "source_message_id": data["source_message_id"],
                "dedupe_key": data["dedupe_key"],
                "event_type": data["event_type"],
                "position_id": data["position_id"],
                "symbol": data["symbol"],
                "state": data.get("state"),
                "qty_base": str(data["qty_base"]) if data.get("qty_base") is not None else None,
                "reason": data.get("reason"),
                "payload": _j(data.get("payload_json")) or {},
                "trace": _j(data.get("trace_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
                "updated_ts": data["updated_ts"].isoformat() if data.get("updated_ts") else None,
            }
        )
    return out


def fetch_live_broker_orders(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM live.orders
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "internal_order_id": str(data["internal_order_id"]),
                "parent_internal_order_id": (
                    str(data["parent_internal_order_id"])
                    if data.get("parent_internal_order_id")
                    else None
                ),
                "source_service": data["source_service"],
                "symbol": data["symbol"],
                "product_type": data["product_type"],
                "margin_mode": data["margin_mode"],
                "margin_coin": data["margin_coin"],
                "side": data["side"],
                "trade_side": data.get("trade_side"),
                "order_type": data["order_type"],
                "force": data.get("force"),
                "reduce_only": bool(data["reduce_only"]),
                "size": str(data["size"]),
                "price": str(data["price"]) if data.get("price") is not None else None,
                "note": data.get("note"),
                "client_oid": data["client_oid"],
                "exchange_order_id": data.get("exchange_order_id"),
                "status": data["status"],
                "last_action": data["last_action"],
                "last_http_status": data.get("last_http_status"),
                "last_exchange_code": data.get("last_exchange_code"),
                "last_exchange_msg": data.get("last_exchange_msg"),
                "last_response": _j(data.get("last_response_json")) or {},
                "trace": _j(data.get("trace_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
                "updated_ts": data["updated_ts"].isoformat() if data.get("updated_ts") else None,
            }
        )
    return out


def fetch_live_broker_fills(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM live.fills
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "internal_order_id": str(data["internal_order_id"]),
                "exchange_order_id": data.get("exchange_order_id"),
                "exchange_trade_id": str(data["exchange_trade_id"]),
                "symbol": data["symbol"],
                "side": data["side"],
                "price": str(data["price"]) if data.get("price") is not None else None,
                "size": str(data["size"]) if data.get("size") is not None else None,
                "fee": str(data["fee"]) if data.get("fee") is not None else None,
                "fee_coin": data.get("fee_coin"),
                "is_maker": bool(data["is_maker"]) if data.get("is_maker") is not None else None,
                "exchange_ts_ms": int(data["exchange_ts_ms"]) if data.get("exchange_ts_ms") is not None else None,
                "raw": _j(data.get("raw_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
            }
        )
    return out


def fetch_live_broker_kill_switch_events(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    if active_only:
        rows = conn.execute(
            """
            SELECT *
            FROM (
                SELECT DISTINCT ON (scope, scope_key) *
                FROM live.kill_switch_events
                WHERE event_type IN ('arm', 'release')
                ORDER BY scope, scope_key, created_ts DESC
            ) latest
            WHERE is_active = true
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM live.kill_switch_events
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "kill_switch_event_id": str(data["kill_switch_event_id"]),
                "scope": data["scope"],
                "scope_key": data["scope_key"],
                "event_type": data["event_type"],
                "is_active": bool(data["is_active"]),
                "source": data["source"],
                "reason": data["reason"],
                "symbol": data.get("symbol"),
                "product_type": data.get("product_type"),
                "margin_coin": data.get("margin_coin"),
                "internal_order_id": (
                    str(data["internal_order_id"]) if data.get("internal_order_id") else None
                ),
                "details": _j(data.get("details_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
            }
        )
    return out


def fetch_live_broker_order_actions(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM live.order_actions
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        oaid = data.get("order_action_id") or data.get("action_id")
        out.append(
            {
                "order_action_id": str(oaid) if oaid is not None else "",
                "internal_order_id": str(data["internal_order_id"]),
                "action": data["action"],
                "request_path": data["request_path"],
                "client_oid": data.get("client_oid"),
                "exchange_order_id": data.get("exchange_order_id"),
                "http_status": data.get("http_status"),
                "exchange_code": data.get("exchange_code"),
                "exchange_msg": data.get("exchange_msg"),
                "retry_count": data.get("retry_count"),
                "request": _j(data.get("request_json")) or {},
                "response": _j(data.get("response_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
            }
        )
    return out


def fetch_live_broker_audit_trails(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
    category: str | None = None,
) -> list[dict[str, Any]]:
    if category:
        rows = conn.execute(
            """
            SELECT *
            FROM live.audit_trails
            WHERE category = %s
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM live.audit_trails
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "audit_trail_id": str(data["audit_trail_id"]),
                "category": data["category"],
                "action": data["action"],
                "severity": data["severity"],
                "scope": data["scope"],
                "scope_key": data["scope_key"],
                "source": data["source"],
                "internal_order_id": (
                    str(data["internal_order_id"]) if data.get("internal_order_id") else None
                ),
                "symbol": data.get("symbol"),
                "details": _j(data.get("details_json")) or {},
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
            }
        )
    return out


def _trunc_json_list(raw: Any, max_items: int) -> list[Any]:
    parsed = _j(raw)
    if not isinstance(parsed, list):
        return []
    return parsed[:max_items]


def fetch_execution_forensic_timeline(
    conn: psycopg.Connection[Any], *, execution_id: str
) -> dict[str, Any] | None:
    """
    Aggregiert Decision, Signal-Kontext, Journal, Operator-Release, Orders, Fills,
    Order-Actions, Shadow/Risk-Sidecars und relevante Audit-Zeilen fuer eine execution_id.
    """
    dec = conn.execute(
        """
        SELECT *
        FROM live.execution_decisions
        WHERE execution_id = %s::uuid
        """,
        (execution_id,),
    ).fetchone()
    if dec is None:
        return None
    ddec = dict(dec)
    payload = _j(ddec.get("payload_json")) or {}
    trace = _j(ddec.get("trace_json")) or {}
    decision_out = _row_public(ddec)
    decision_out["payload_json"] = redact_nested_mapping(payload, max_depth=4)
    decision_out["trace_json"] = redact_nested_mapping(trace, max_depth=4)

    rel = conn.execute(
        """
        SELECT *
        FROM live.execution_operator_releases
        WHERE execution_id = %s::uuid
        """,
        (execution_id,),
    ).fetchone()
    operator_release = _row_public(dict(rel)) if rel is not None else None

    journal_rows = conn.execute(
        """
        SELECT journal_id, execution_decision_id, internal_order_id, phase, details_json, created_ts
        FROM live.execution_journal
        WHERE execution_decision_id = %s::uuid
        ORDER BY created_ts ASC
        """,
        (execution_id,),
    ).fetchall()
    journal: list[dict[str, Any]] = []
    for jr in journal_rows:
        jd = dict(jr)
        journal.append(
            {
                "journal_id": str(jd["journal_id"]),
                "execution_decision_id": str(jd["execution_decision_id"])
                if jd.get("execution_decision_id")
                else None,
                "internal_order_id": str(jd["internal_order_id"])
                if jd.get("internal_order_id")
                else None,
                "phase": jd.get("phase"),
                "details_json": redact_nested_mapping(_j(jd.get("details_json")) or {}, max_depth=5),
                "created_ts": jd["created_ts"].isoformat() if jd.get("created_ts") else None,
            }
        )

    sig_block: dict[str, Any] | None = None
    sid = ddec.get("source_signal_id")
    if sid is not None:
        sr = conn.execute(
            """
            SELECT s.signal_id, s.symbol, s.timeframe, s.direction, s.market_family, s.canonical_instrument_id,
                   s.trade_action, s.decision_state, s.meta_trade_lane, s.playbook_id, s.playbook_family,
                   s.playbook_decision_mode, s.strategy_name, s.regime_state,
                   s.stop_fragility_0_1, s.stop_executability_0_1, s.stop_distance_pct,
                   s.stop_budget_max_pct_allowed, s.stop_min_executable_pct, s.stop_quality_0_1,
                   s.stop_to_spread_ratio, s.model_uncertainty_0_1, s.shadow_divergence_0_1,
                   s.expected_return_bps, s.expected_mae_bps, s.expected_mfe_bps,
                   s.abstention_reasons_json, s.rejection_reasons_json, s.leverage_cap_reasons_json,
                   s.reasons_json, s.source_snapshot_json, s.analysis_ts_ms, s.created_at,
                   e.explain_short, e.explain_long_md, e.risk_warnings_json
            FROM app.signals_v1 s
            LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
            WHERE s.signal_id = %s::uuid
            """,
            (str(sid),),
        ).fetchone()
        if sr is not None:
            sd = dict(sr)
            reasons_json = _j(sd.get("reasons_json")) or {}
            source_snapshot = _j(sd.get("source_snapshot_json")) or {}
            sig_block = {
                "signal_id": str(sd["signal_id"]),
                "symbol": sd.get("symbol"),
                "timeframe": sd.get("timeframe"),
                "direction": sd.get("direction"),
                "market_family": sd.get("market_family"),
                "canonical_instrument_id": sd.get("canonical_instrument_id"),
                "trade_action": sd.get("trade_action"),
                "decision_state": sd.get("decision_state"),
                "meta_trade_lane": sd.get("meta_trade_lane"),
                "playbook_id": sd.get("playbook_id"),
                "playbook_family": sd.get("playbook_family"),
                "playbook_decision_mode": sd.get("playbook_decision_mode"),
                "strategy_name": sd.get("strategy_name"),
                "regime_state": sd.get("regime_state"),
                "stop_fragility_0_1": float(sd["stop_fragility_0_1"])
                if sd.get("stop_fragility_0_1") is not None
                else None,
                "stop_executability_0_1": float(sd["stop_executability_0_1"])
                if sd.get("stop_executability_0_1") is not None
                else None,
                "stop_distance_pct": float(sd["stop_distance_pct"])
                if sd.get("stop_distance_pct") is not None
                else None,
                "stop_budget_max_pct_allowed": float(sd["stop_budget_max_pct_allowed"])
                if sd.get("stop_budget_max_pct_allowed") is not None
                else None,
                "stop_min_executable_pct": float(sd["stop_min_executable_pct"])
                if sd.get("stop_min_executable_pct") is not None
                else None,
                "stop_quality_0_1": float(sd["stop_quality_0_1"])
                if sd.get("stop_quality_0_1") is not None
                else None,
                "stop_to_spread_ratio": float(sd["stop_to_spread_ratio"])
                if sd.get("stop_to_spread_ratio") is not None
                else None,
                "model_uncertainty_0_1": float(sd["model_uncertainty_0_1"])
                if sd.get("model_uncertainty_0_1") is not None
                else None,
                "shadow_divergence_0_1": float(sd["shadow_divergence_0_1"])
                if sd.get("shadow_divergence_0_1") is not None
                else None,
                "expected_return_bps": float(sd["expected_return_bps"])
                if sd.get("expected_return_bps") is not None
                else None,
                "expected_mae_bps": float(sd["expected_mae_bps"])
                if sd.get("expected_mae_bps") is not None
                else None,
                "expected_mfe_bps": float(sd["expected_mfe_bps"])
                if sd.get("expected_mfe_bps") is not None
                else None,
                "abstention_reasons_json": _trunc_json_list(sd.get("abstention_reasons_json"), 20),
                "rejection_reasons_json": _trunc_json_list(sd.get("rejection_reasons_json"), 20),
                "leverage_cap_reasons_json": _trunc_json_list(sd.get("leverage_cap_reasons_json"), 16),
                "reasons_json": redact_nested_mapping(reasons_json, max_depth=4),
                "source_snapshot_json": redact_nested_mapping(source_snapshot, max_depth=4),
                "explain_short": sd.get("explain_short"),
                "explain_long_md": (str(sd.get("explain_long_md") or "")[:4000] or None),
                "risk_warnings_json": _trunc_json_list(sd.get("risk_warnings_json"), 16),
                "analysis_ts_ms": int(sd["analysis_ts_ms"]) if sd.get("analysis_ts_ms") is not None else None,
                "created_ts": sd["created_at"].isoformat() if sd.get("created_at") else None,
            }

    orders_rows = conn.execute(
        """
        SELECT *
        FROM live.orders
        WHERE source_execution_decision_id = %s::uuid
        ORDER BY created_ts ASC
        """,
        (execution_id,),
    ).fetchall()
    orders: list[dict[str, Any]] = []
    order_ids: list[str] = []
    for orow in orders_rows:
        od = dict(orow)
        oid = str(od["internal_order_id"])
        order_ids.append(oid)
        o_pub = _row_public(od)
        o_pub["last_response_json"] = redact_nested_mapping(_j(od.get("last_response_json")) or {}, max_depth=3)
        o_pub["trace_json"] = redact_nested_mapping(_j(od.get("trace_json")) or {}, max_depth=3)
        orders.append(o_pub)

    fills: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    if order_ids:
        frows = conn.execute(
            """
            SELECT fill_id, internal_order_id, exchange_order_id, exchange_trade_id, symbol, side,
                   price, size, fee, fee_coin, is_maker, exchange_ts_ms, created_ts
            FROM live.fills
            WHERE internal_order_id = ANY(%s::uuid[])
            ORDER BY created_ts ASC
            """,
            (order_ids,),
        ).fetchall()
        fills = [_row_public(dict(fr)) for fr in frows]

        act_rows = conn.execute(
            """
            SELECT action_id AS order_action_id, internal_order_id, action, request_path, http_status,
                   exchange_code, exchange_msg, retry_count, request_json, response_json, created_ts
            FROM live.order_actions
            WHERE internal_order_id = ANY(%s::uuid[])
            ORDER BY created_ts ASC
            """,
            (order_ids,),
        ).fetchall()
        for ar in act_rows:
            ad = dict(ar)
            actions.append(
                {
                    "order_action_id": str(ad["order_action_id"]),
                    "internal_order_id": str(ad["internal_order_id"]),
                    "action": ad.get("action"),
                    "request_path": ad.get("request_path"),
                    "http_status": ad.get("http_status"),
                    "exchange_code": ad.get("exchange_code"),
                    "exchange_msg": ad.get("exchange_msg"),
                    "retry_count": ad.get("retry_count"),
                    "request_json": redact_nested_mapping(_j(ad.get("request_json")) or {}, max_depth=3),
                    "response_json": redact_nested_mapping(_j(ad.get("response_json")) or {}, max_depth=3),
                    "created_ts": ad["created_ts"].isoformat() if ad.get("created_ts") else None,
                }
            )

    audits: list[dict[str, Any]] = []
    if order_ids:
        aud_rows = conn.execute(
            """
            SELECT audit_trail_id, category, action, severity, scope, scope_key, source,
                   internal_order_id, symbol, details_json, created_ts
            FROM live.audit_trails
            WHERE internal_order_id = ANY(%s::uuid[])
            ORDER BY created_ts ASC
            """,
            (order_ids,),
        ).fetchall()
        for ar in aud_rows:
            ad = dict(ar)
            audits.append(
                {
                    "audit_trail_id": str(ad["audit_trail_id"]),
                    "category": ad.get("category"),
                    "action": ad.get("action"),
                    "severity": ad.get("severity"),
                    "scope": ad.get("scope"),
                    "scope_key": ad.get("scope_key"),
                    "source": ad.get("source"),
                    "internal_order_id": str(ad["internal_order_id"])
                    if ad.get("internal_order_id")
                    else None,
                    "symbol": ad.get("symbol"),
                    "details": redact_nested_mapping(_j(ad.get("details_json")) or {}, max_depth=4),
                    "created_ts": ad["created_ts"].isoformat() if ad.get("created_ts") else None,
                }
            )

    shadow = conn.execute(
        """
        SELECT *
        FROM live.shadow_live_assessments
        WHERE execution_decision_id = %s::uuid
        """,
        (execution_id,),
    ).fetchone()
    shadow_assessment: dict[str, Any] | None = None
    if shadow is not None:
        sdict = dict(shadow)
        shadow_assessment = _row_public(sdict)
        shadow_assessment["report_json"] = redact_nested_mapping(
            _j(sdict.get("report_json")) or {}, max_depth=4
        )

    risk = conn.execute(
        """
        SELECT *
        FROM live.execution_risk_snapshots
        WHERE execution_decision_id = %s::uuid
        """,
        (execution_id,),
    ).fetchone()
    risk_snapshot = None
    if risk is not None:
        rd = dict(risk)
        risk_snapshot = _row_public(rd)
        risk_snapshot["detail_json"] = redact_nested_mapping(_j(rd.get("detail_json")) or {}, max_depth=4)
        risk_snapshot["reasons_json"] = _trunc_json_list(_j(rd.get("reasons_json")), 24)
        risk_snapshot["metrics_json"] = redact_nested_mapping(_j(rd.get("metrics_json")) or {}, max_depth=3)

    learning_e2e_record: dict[str, Any] | None = None
    paper_positions: list[dict[str, Any]] = []
    trade_reviews: list[dict[str, Any]] = []
    telegram_operator_actions: list[dict[str, Any]] = []
    telegram_alert_outbox: list[dict[str, Any]] = []
    gateway_audit_trails: list[dict[str, Any]] = []
    exit_plans: list[dict[str, Any]] = []
    sid_text = str(sid) if sid is not None else None

    if sid_text is not None:
        e2e = conn.execute(
            """
            SELECT record_id, signal_id, schema_version, decision_ts_ms,
                   canonical_instrument_id, symbol, timeframe, market_family,
                   playbook_id, playbook_family, regime_label, meta_trade_lane, trade_action,
                   paper_trade_id, shadow_trade_id, live_mirror_trade_id, trade_evaluation_id,
                   snapshot_json, outcomes_json, label_qc_json, operator_mirror_actions_json,
                   created_ts, updated_ts
            FROM learn.e2e_decision_records
            WHERE signal_id = %s::uuid
            LIMIT 1
            """,
            (sid_text,),
        ).fetchone()
        if e2e is not None:
            ed = dict(e2e)
            learning_e2e_record = {
                "record_id": str(ed["record_id"]),
                "signal_id": str(ed["signal_id"]),
                "schema_version": ed.get("schema_version"),
                "decision_ts_ms": _i(ed.get("decision_ts_ms")),
                "canonical_instrument_id": ed.get("canonical_instrument_id"),
                "symbol": ed.get("symbol"),
                "timeframe": ed.get("timeframe"),
                "market_family": ed.get("market_family"),
                "playbook_id": ed.get("playbook_id"),
                "playbook_family": ed.get("playbook_family"),
                "regime_label": ed.get("regime_label"),
                "meta_trade_lane": ed.get("meta_trade_lane"),
                "trade_action": ed.get("trade_action"),
                "paper_trade_id": str(ed["paper_trade_id"]) if ed.get("paper_trade_id") else None,
                "shadow_trade_id": str(ed["shadow_trade_id"]) if ed.get("shadow_trade_id") else None,
                "live_mirror_trade_id": str(ed["live_mirror_trade_id"])
                if ed.get("live_mirror_trade_id")
                else None,
                "trade_evaluation_id": str(ed["trade_evaluation_id"])
                if ed.get("trade_evaluation_id")
                else None,
                "snapshot_json": redact_nested_mapping(_j(ed.get("snapshot_json")) or {}, max_depth=4),
                "outcomes_json": redact_nested_mapping(_j(ed.get("outcomes_json")) or {}, max_depth=4),
                "label_qc_json": redact_nested_mapping(_j(ed.get("label_qc_json")) or {}, max_depth=4),
                "operator_mirror_actions_json": redact_nested_mapping(
                    _j(ed.get("operator_mirror_actions_json")) or [],
                    max_depth=4,
                ),
                "created_ts": ed["created_ts"].isoformat() if ed.get("created_ts") else None,
                "updated_ts": ed["updated_ts"].isoformat() if ed.get("updated_ts") else None,
            }

        pos_rows = conn.execute(
            """
            SELECT position_id, signal_id, symbol, side, state, qty_base, entry_price_avg,
                   leverage, opened_ts_ms, closed_ts_ms, canonical_instrument_id, market_family,
                   product_type, stop_plan_json, tp_plan_json, stop_quality_score, rr_estimate,
                   plan_updated_ts_ms, meta, tenant_id
            FROM paper.positions
            WHERE signal_id = %s::uuid
            ORDER BY opened_ts_ms DESC
            LIMIT 8
            """,
            (sid_text,),
        ).fetchall()
        paper_positions = [
            {
                "position_id": str(dict(r)["position_id"]),
                "signal_id": str(dict(r)["signal_id"]) if dict(r).get("signal_id") else None,
                "tenant_id": dict(r).get("tenant_id"),
                "symbol": dict(r).get("symbol"),
                "side": dict(r).get("side"),
                "state": dict(r).get("state"),
                "qty_base": str(dict(r)["qty_base"]) if dict(r).get("qty_base") is not None else None,
                "entry_price_avg": str(dict(r)["entry_price_avg"])
                if dict(r).get("entry_price_avg") is not None
                else None,
                "leverage": str(dict(r)["leverage"]) if dict(r).get("leverage") is not None else None,
                "opened_ts_ms": _i(dict(r).get("opened_ts_ms")),
                "closed_ts_ms": _i(dict(r).get("closed_ts_ms")),
                "canonical_instrument_id": dict(r).get("canonical_instrument_id"),
                "market_family": dict(r).get("market_family"),
                "product_type": dict(r).get("product_type"),
                "stop_plan_json": redact_nested_mapping(_j(dict(r).get("stop_plan_json")) or {}, max_depth=3),
                "tp_plan_json": redact_nested_mapping(_j(dict(r).get("tp_plan_json")) or {}, max_depth=3),
                "stop_quality_score": dict(r).get("stop_quality_score"),
                "rr_estimate": str(dict(r)["rr_estimate"]) if dict(r).get("rr_estimate") is not None else None,
                "plan_updated_ts_ms": _i(dict(r).get("plan_updated_ts_ms")),
                "meta": redact_nested_mapping(_j(dict(r).get("meta")) or {}, max_depth=3),
            }
            for r in pos_rows
        ]

        eval_rows = conn.execute(
            """
            SELECT evaluation_id, paper_trade_id, signal_id, symbol, timeframe,
                   opened_ts_ms, closed_ts_ms, side, pnl_net_usdt, direction_correct,
                   stop_hit, tp1_hit, tp2_hit, tp3_hit, time_to_tp1_ms, time_to_stop_ms,
                   stop_quality_score, slippage_bps_entry, slippage_bps_exit,
                   error_labels_json, signal_snapshot_json, feature_snapshot_json,
                   structure_snapshot_json, created_ts
            FROM learn.trade_evaluations
            WHERE signal_id = %s::uuid
            ORDER BY created_ts DESC
            LIMIT 8
            """,
            (sid_text,),
        ).fetchall()
        trade_reviews = [
            {
                "evaluation_id": str(dict(r)["evaluation_id"]),
                "paper_trade_id": str(dict(r)["paper_trade_id"]),
                "signal_id": str(dict(r)["signal_id"]) if dict(r).get("signal_id") else None,
                "symbol": dict(r).get("symbol"),
                "timeframe": dict(r).get("timeframe"),
                "opened_ts_ms": _i(dict(r).get("opened_ts_ms")),
                "closed_ts_ms": _i(dict(r).get("closed_ts_ms")),
                "side": dict(r).get("side"),
                "pnl_net_usdt": float(dict(r)["pnl_net_usdt"])
                if dict(r).get("pnl_net_usdt") is not None
                else None,
                "direction_correct": dict(r).get("direction_correct"),
                "stop_hit": dict(r).get("stop_hit"),
                "tp1_hit": dict(r).get("tp1_hit"),
                "tp2_hit": dict(r).get("tp2_hit"),
                "tp3_hit": dict(r).get("tp3_hit"),
                "time_to_tp1_ms": _i(dict(r).get("time_to_tp1_ms")),
                "time_to_stop_ms": _i(dict(r).get("time_to_stop_ms")),
                "stop_quality_score": dict(r).get("stop_quality_score"),
                "slippage_bps_entry": float(dict(r)["slippage_bps_entry"])
                if dict(r).get("slippage_bps_entry") is not None
                else None,
                "slippage_bps_exit": float(dict(r)["slippage_bps_exit"])
                if dict(r).get("slippage_bps_exit") is not None
                else None,
                "error_labels_json": _trunc_json_list(dict(r).get("error_labels_json"), 12),
                "signal_snapshot_json": redact_nested_mapping(
                    _j(dict(r).get("signal_snapshot_json")) or {},
                    max_depth=3,
                ),
                "feature_snapshot_json": redact_nested_mapping(
                    _j(dict(r).get("feature_snapshot_json")) or {},
                    max_depth=3,
                ),
                "structure_snapshot_json": redact_nested_mapping(
                    _j(dict(r).get("structure_snapshot_json")) or {},
                    max_depth=3,
                ),
                "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
            }
            for r in eval_rows
        ]

    tga_rows = conn.execute(
        """
        SELECT audit_id, ts, outcome, action_kind, execution_id, pending_id, http_status, details_json
        FROM alert.operator_action_audit
        WHERE execution_id = %s::uuid
        ORDER BY ts ASC
        LIMIT 100
        """,
        (execution_id,),
    ).fetchall()
    telegram_operator_actions = [
        {
            "audit_id": str(dict(r)["audit_id"]),
            "ts": dict(r)["ts"].isoformat() if dict(r).get("ts") else None,
            "outcome": dict(r).get("outcome"),
            "action_kind": dict(r).get("action_kind"),
            "execution_id": str(dict(r)["execution_id"]) if dict(r).get("execution_id") else None,
            "pending_id": str(dict(r)["pending_id"]) if dict(r).get("pending_id") else None,
            "http_status": dict(r).get("http_status"),
            "details_json": redact_nested_mapping(_j(dict(r).get("details_json")) or {}, max_depth=4),
        }
        for r in tga_rows
    ]

    outbox_rows = conn.execute(
        """
        SELECT alert_id, alert_type, severity, state, telegram_message_id, attempt_count,
               last_error, sent_ts, created_ts, payload
        FROM alert.alert_outbox
        WHERE (payload->>'execution_id') = %s
           OR (%s::text IS NOT NULL AND (payload->>'signal_id') = %s)
        ORDER BY created_ts ASC
        LIMIT 100
        """,
        (execution_id, sid_text, sid_text),
    ).fetchall()
    telegram_alert_outbox = [
        {
            "alert_id": str(dict(r)["alert_id"]),
            "alert_type": dict(r).get("alert_type"),
            "severity": dict(r).get("severity"),
            "state": dict(r).get("state"),
            "telegram_message_id": dict(r).get("telegram_message_id"),
            "attempt_count": dict(r).get("attempt_count"),
            "last_error": dict(r).get("last_error"),
            "sent_ts": dict(r)["sent_ts"].isoformat() if dict(r).get("sent_ts") else None,
            "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
            "payload": redact_nested_mapping(_j(dict(r).get("payload")) or {}, max_depth=4),
        }
        for r in outbox_rows
    ]

    gate_rows = conn.execute(
        """
        SELECT id, created_ts, actor, auth_method, action, http_method, path, detail_json
        FROM app.gateway_request_audit
        WHERE (detail_json->>'execution_id') = %s
          AND action IN (
              'manual_action_token_minted',
              'live_broker_operator_release_mutate',
              'auth_failure_manual_action_token',
              'auth_failure_live_broker_mutation',
              'auth_failure_live_broker_mutation_role'
          )
        ORDER BY created_ts ASC
        LIMIT 100
        """,
        (execution_id,),
    ).fetchall()
    gateway_audit_trails = [
        {
            "id": str(dict(r)["id"]),
            "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
            "actor": dict(r).get("actor"),
            "auth_method": dict(r).get("auth_method"),
            "action": dict(r).get("action"),
            "http_method": dict(r).get("http_method"),
            "path": dict(r).get("path"),
            "detail_json": redact_nested_mapping(_j(dict(r).get("detail_json")) or {}, max_depth=4),
        }
        for r in gate_rows
    ]

    if order_ids or sid_text is not None:
        exit_rows = conn.execute(
            """
            SELECT plan_id, root_internal_order_id, source_signal_id, symbol, side, timeframe, state,
                   entry_price, initial_qty, remaining_qty, stop_plan_json, tp_plan_json,
                   context_json, last_market_json, last_decision_json, last_reason,
                   created_ts, updated_ts, closed_ts
            FROM live.exit_plans
            WHERE (%s::text IS NOT NULL AND source_signal_id = %s)
               OR (%s::uuid[] IS NOT NULL AND root_internal_order_id = ANY(%s::uuid[]))
            ORDER BY updated_ts ASC NULLS LAST, created_ts ASC
            LIMIT 32
            """,
            (sid_text, sid_text, order_ids or None, order_ids or None),
        ).fetchall()
        exit_plans = [
            {
                "plan_id": str(dict(r)["plan_id"]),
                "root_internal_order_id": str(dict(r)["root_internal_order_id"])
                if dict(r).get("root_internal_order_id")
                else None,
                "source_signal_id": dict(r).get("source_signal_id"),
                "symbol": dict(r).get("symbol"),
                "side": dict(r).get("side"),
                "timeframe": dict(r).get("timeframe"),
                "state": dict(r).get("state"),
                "entry_price": str(dict(r)["entry_price"]) if dict(r).get("entry_price") is not None else None,
                "initial_qty": str(dict(r)["initial_qty"]) if dict(r).get("initial_qty") is not None else None,
                "remaining_qty": str(dict(r)["remaining_qty"])
                if dict(r).get("remaining_qty") is not None
                else None,
                "stop_plan_json": redact_nested_mapping(_j(dict(r).get("stop_plan_json")) or {}, max_depth=4),
                "tp_plan_json": redact_nested_mapping(_j(dict(r).get("tp_plan_json")) or {}, max_depth=4),
                "context_json": redact_nested_mapping(_j(dict(r).get("context_json")) or {}, max_depth=4),
                "last_market_json": redact_nested_mapping(_j(dict(r).get("last_market_json")) or {}, max_depth=4),
                "last_decision_json": redact_nested_mapping(_j(dict(r).get("last_decision_json")) or {}, max_depth=4),
                "last_reason": dict(r).get("last_reason"),
                "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
                "updated_ts": dict(r)["updated_ts"].isoformat() if dict(r).get("updated_ts") else None,
                "closed_ts": dict(r)["closed_ts"].isoformat() if dict(r).get("closed_ts") else None,
            }
            for r in exit_rows
        ]

    events: list[dict[str, Any]] = []
    if sig_block:
        events.append(
            {
                "ts": sig_block.get("created_ts"),
                "kind": "signal_context",
                "ref": sig_block.get("signal_id"),
                "summary": {
                    "trade_action": sig_block.get("trade_action"),
                    "decision_state": sig_block.get("decision_state"),
                    "router_id": (
                        ((_j(sig_block.get("reasons_json")) or {}).get("specialists") or {})
                        .get("router_arbitration", {})
                        .get("router_id")
                        if isinstance((_j(sig_block.get("reasons_json")) or {}).get("specialists"), dict)
                        else None
                    ),
                    "playbook_id": sig_block.get("playbook_id"),
                },
            }
        )
        events.append(
            {
                "ts": sig_block.get("created_ts"),
                "kind": "specialist_path_marker",
                "ref": sig_block.get("signal_id"),
                "summary": {
                    "detail_key": "signal_path_summary",
                    "note_de": "Kompakte Spezialisten/Router/DCF in signal_path_summary (Journal-Redaction).",
                },
            }
        )
    events.append(
        {
            "ts": decision_out.get("created_ts"),
            "kind": "execution_decision",
            "ref": execution_id,
            "summary": {
                "action": decision_out.get("decision_action"),
                "reason": decision_out.get("decision_reason"),
                "effective_mode": decision_out.get("effective_runtime_mode"),
            },
        }
    )
    if learning_e2e_record:
        events.append(
            {
                "ts": learning_e2e_record.get("created_ts") or learning_e2e_record.get("updated_ts"),
                "kind": "learning_e2e_record",
                "ref": learning_e2e_record.get("record_id"),
                "summary": {
                    "trade_action": learning_e2e_record.get("trade_action"),
                    "meta_trade_lane": learning_e2e_record.get("meta_trade_lane"),
                    "paper_trade_id": learning_e2e_record.get("paper_trade_id"),
                },
            }
        )
    if operator_release:
        events.append(
            {
                "ts": operator_release.get("created_ts"),
                "kind": "operator_release",
                "ref": execution_id,
                "summary": {"source": operator_release.get("source")},
            }
        )
    for j in journal:
        events.append(
            {
                "ts": j.get("created_ts"),
                "kind": f"journal:{j.get('phase')}",
                "ref": j.get("journal_id"),
                "summary": {"phase": j.get("phase")},
            }
        )
    for o in orders:
        events.append(
            {
                "ts": o.get("created_ts"),
                "kind": "order",
                "ref": o.get("internal_order_id"),
                "summary": {"status": o.get("status"), "side": o.get("side")},
            }
        )
    for f in fills:
        events.append(
            {
                "ts": f.get("created_ts"),
                "kind": "fill",
                "ref": f.get("exchange_trade_id"),
                "summary": {"symbol": f.get("symbol"), "side": f.get("side")},
            }
        )
    for plan in exit_plans:
        events.append(
            {
                "ts": plan.get("updated_ts") or plan.get("created_ts"),
                "kind": "exit_plan",
                "ref": plan.get("plan_id"),
                "summary": {"state": plan.get("state"), "last_reason": plan.get("last_reason")},
            }
        )
    for paper_pos in paper_positions:
        events.append(
            {
                "ts": _ts_ms_to_iso(paper_pos.get("closed_ts_ms") or paper_pos.get("opened_ts_ms")),
                "kind": "paper_position",
                "ref": paper_pos.get("position_id"),
                "summary": {"state": paper_pos.get("state"), "side": paper_pos.get("side")},
            }
        )
    for review in trade_reviews:
        events.append(
            {
                "ts": review.get("created_ts"),
                "kind": "trade_review",
                "ref": review.get("evaluation_id"),
                "summary": {
                    "pnl_net_usdt": review.get("pnl_net_usdt"),
                    "direction_correct": review.get("direction_correct"),
                    "stop_hit": review.get("stop_hit"),
                },
            }
        )
    for action in telegram_operator_actions:
        events.append(
            {
                "ts": action.get("ts"),
                "kind": "telegram_operator_action",
                "ref": action.get("audit_id"),
                "summary": {"outcome": action.get("outcome"), "action_kind": action.get("action_kind")},
            }
        )
    for msg in telegram_alert_outbox:
        events.append(
            {
                "ts": msg.get("sent_ts") or msg.get("created_ts"),
                "kind": "telegram_outbox",
                "ref": msg.get("alert_id"),
                "summary": {"alert_type": msg.get("alert_type"), "state": msg.get("state")},
            }
        )
    for audit in gateway_audit_trails:
        events.append(
            {
                "ts": audit.get("created_ts"),
                "kind": "gateway_audit",
                "ref": audit.get("id"),
                "summary": {"action": audit.get("action"), "auth_method": audit.get("auth_method")},
            }
        )
    events.sort(key=lambda e: (e.get("ts") is None, e.get("ts") or ""))

    forensic_phases = build_forensic_timeline_phases(events)
    signal_path_summary = None
    trace_for_snap: dict[str, Any] | None = None
    tr_raw = decision_out.get("trace_json")
    tr_parsed = _j(tr_raw) if tr_raw is not None else None
    if isinstance(tr_parsed, dict):
        trace_for_snap = tr_parsed
    if sig_block:
        signal_path_summary = build_live_broker_forensic_snapshot(
            signal_payload=sig_block,
            risk_decision=risk_snapshot if isinstance(risk_snapshot, dict) else None,
            shadow_live_report=shadow_assessment if isinstance(shadow_assessment, dict) else None,
            trace=trace_for_snap,
        )
    corr_chain = None
    if sig_block:
        snap = _j(sig_block.get("source_snapshot_json"))
        if isinstance(snap, dict):
            cc = snap.get("correlation_chain")
            corr_chain = cc if isinstance(cc, dict) else None

    out: dict[str, Any] = {
        "execution_id": execution_id,
        "decision": decision_out,
        "signal_context": sig_block,
        "operator_release": operator_release,
        "journal": journal,
        "orders": orders,
        "fills": fills,
        "exit_plans": exit_plans,
        "order_actions": actions,
        "audit_trails": audits,
        "shadow_live_assessment": shadow_assessment,
        "risk_snapshot": risk_snapshot,
        "learning_e2e_record": learning_e2e_record,
        "paper_positions": paper_positions,
        "trade_reviews": trade_reviews,
        "telegram_operator_actions": telegram_operator_actions,
        "telegram_alert_outbox": telegram_alert_outbox,
        "gateway_audit_trails": gateway_audit_trails,
        "timeline_sorted": events,
        "forensic_phases": forensic_phases,
        "signal_path_summary": signal_path_summary,
        "correlation": {
            "execution_id": execution_id,
            "signal_id": str(sid) if sid is not None else None,
            "correlation_chain": corr_chain,
        },
        "forensic_model_version": "forensic-timeline-v3",
        "schema_version": 3,
    }
    out = _attach_apex_trade_forensic_golden_record(conn, out)
    return out


def _attach_apex_trade_forensic_golden_record(
    conn: psycopg.Connection[Any], timeline: dict[str, Any]
) -> dict[str, Any]:
    from psycopg import errors as pg_errors

    from shared_py.observability.apex_trade_forensic_store import (
        expected_previous_chain_for_row,
        fetch_apex_trade_forensic_row,
        upsert_apex_trade_forensic,
        verify_row_integrity,
    )
    from shared_py.observability.trade_lifecycle_audit import build_golden_record_from_timeline

    ex = str(timeline.get("execution_id") or "")
    if not ex:
        timeline["apex_trade_forensic"] = None
        return timeline
    tenant_apex: str = "default"
    dec0 = timeline.get("decision")
    if isinstance(dec0, dict):
        tj0 = _j(dec0.get("trace_json"))
        if isinstance(tj0, dict) and tj0.get("tenant_id"):
            tenant_apex = str(tj0["tenant_id"]).strip() or "default"
    pps0 = timeline.get("paper_positions")
    if (
        tenant_apex == "default"
        and isinstance(pps0, list)
        and pps0
        and isinstance(pps0[0], dict)
        and pps0[0].get("tenant_id")
    ):
        tenant_apex = str(pps0[0]["tenant_id"]).strip() or "default"
    cor = timeline.get("correlation")
    cor = cor if isinstance(cor, dict) else {}
    signal_id: str | None = cor.get("signal_id")
    if signal_id is not None:
        signal_id = str(signal_id)
    try:
        golden = build_golden_record_from_timeline(timeline)
        m = upsert_apex_trade_forensic(
            conn,
            execution_id=ex,
            signal_id=signal_id,
            golden_record=golden,
            tenant_id=tenant_apex,
        )
        row = fetch_apex_trade_forensic_row(conn, execution_id=ex)
    except (pg_errors.Error, OSError, RuntimeError, ValueError, TypeError) as e:
        timeline["apex_trade_forensic"] = {
            "ok": False,
            "error": str(e)[:200],
        }
        return timeline

    is_ver: dict[str, Any] = {"is_verified": False}
    gr0 = row.get("golden_record") if row else None
    g: dict[str, Any] = gr0 if isinstance(gr0, dict) else golden
    if row:
        try:
            rid = int(row["id"])
            expect_prev = expected_previous_chain_for_row(conn, row_id=rid)
            is_ver = verify_row_integrity(row, expected_prev_link=expect_prev)
        except (TypeError, KeyError, ValueError, AttributeError):
            is_ver = {"is_verified": False, "error": "verify_failed"}
    pr = row.get("prev_chain_checksum") if row else None
    ch = row.get("chain_checksum") if row else None
    if isinstance(pr, memoryview):
        pr = pr.tobytes()
    if isinstance(ch, memoryview):
        ch = ch.tobytes()
    stored = row is not None
    timeline["apex_trade_forensic"] = {
        "ok": stored,
        "materialize": m,
        "is_verified": is_ver.get("is_verified") if stored else False,
        "verification": is_ver,
        "golden_record": g if isinstance(g, dict) else None,
        "chain_checksum_hex": ch.hex() if isinstance(ch, (bytes, memoryview)) else None,
        "prev_chain_checksum_hex": pr.hex() if isinstance(pr, (bytes, memoryview)) else None,
    }
    return timeline


def fetch_ops_risk_assist_context(
    conn: psycopg.Connection[Any], *, execution_id: str
) -> dict[str, Any] | None:
    """Kontext fuer Multiturn ops_risk Assist (Golden Record + Policy-Treffer)."""
    from shared_py.observability.risk_rejection_inquiry import build_ops_risk_assist_context

    row = fetch_execution_forensic_timeline(conn, execution_id=execution_id)
    if row is None:
        return None
    return build_ops_risk_assist_context(row)
