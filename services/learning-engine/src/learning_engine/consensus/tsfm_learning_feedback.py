"""
TSFM / War-Room -> Learning: Konsensmetriken aus app.apex_audit_ledger (Migration 617)
in Trainingsbeispiele spiegeln (consensus_penalty, uncertainty_weight).

Voraussetzung: trade_evaluations.signal_id passt zu market_event_json.signal_id
im canonical_payload der Ledger-Eintraege.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors

logger = logging.getLogger("learning_engine.consensus.tsfm_learning_feedback")

_HARDFAIL_UNCERTAINTY_BONUS = 2.0


def specialist_disagreement_from_war_room(wr: Mapping[str, Any] | None) -> bool:
    """
    "Specialist Disagreement" im Sinne des War-Room: Macro vs Quant hoch, oder
    expliziter high_uncertainty-Status (vgl. war_room.ConsensusOrchestrator).
    """
    if not wr:
        return False
    if bool(wr.get("macro_quant_high_uncertainty")):
        return True
    if str(wr.get("consensus_status") or "").strip() == "high_uncertainty":
        return True
    return False


def _parse_apex_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row.get("canonical_payload_text")
    if not raw or not str(raw).strip():
        return None
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return None


def _signal_id_from_apex_record(rec: dict[str, Any]) -> str | None:
    me = rec.get("market_event_json")
    if not isinstance(me, dict):
        return None
    v = me.get("signal_id")
    if v is not None and str(v).strip():
        return str(v).lower()
    sig = me.get("signal")
    if isinstance(sig, dict) and sig.get("signal_id") is not None:
        return str(sig.get("signal_id")).lower()
    return None


def _war_room_from_record(rec: dict[str, Any] | None) -> dict[str, Any] | None:
    if not rec:
        return None
    wr = rec.get("war_room")
    return wr if isinstance(wr, dict) else None


def consensus_to_labels(
    war_room: Mapping[str, Any] | None,
    *,
    pnl_net_usdt: float,
    has_signal_link: bool,
) -> tuple[float, float]:
    """
    Mapt Konsens + Outcome auf consensus_penalty und uncertainty_weight (Sample-Gewicht).

    Harte Lehre: Spezialisten laut Ledger uneinig (bzw. high uncertainty), Trade real
    ausgefuehrt, Verlust -> consensus_penalty=1.0, Groessenordnung der Nachschaerfung
    via uncertainty_weight (1 + Bonus).

    Returns:
        (consensus_penalty 0..1, uncertainty_weight >= 1.0)
    """
    d = specialist_disagreement_from_war_room(war_room)
    loss = pnl_net_usdt < 0.0
    if not has_signal_link:
        return 0.0, 1.0
    if d and loss:
        return 1.0, 1.0 + _HARDFAIL_UNCERTAINTY_BONUS
    if d and not loss:
        return 0.25, 1.25
    return 0.0, 1.0


def _fetch_by_signal_json_path(
    conn: psycopg.Connection[Any],
    signal_id_strs: list[str],
) -> list[dict[str, Any]]:
    """Kannonisches JSON: signal_id in market_event_json. Kein GIN-Index noetig fuer Batches."""
    uuids = [UUID(s) for s in signal_id_strs]
    if not uuids:
        return []
    rows = conn.execute(
        """
        SELECT
            e.id, e.decision_id, e.created_at, e.canonical_payload_text
        FROM app.apex_audit_ledger_entries e
        CROSS JOIN LATERAL (
            SELECT (e.canonical_payload_text::json->'market_event_json'->>'signal_id')::uuid AS sig
        ) x
        WHERE x.sig = ANY(%s)
        ORDER BY e.id DESC
        """,
        (uuids,),
    ).fetchall()
    return [dict(r) for r in rows]


def _index_war_room_by_signal(
    raw_rows: list[dict[str, Any]],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    """
    Pro signal_id (Kleinbuchstaben): Ledger-Verknuepfung und War-Room-Dict
    (erste Zeile = juengster Eintrag, ORDER BY id DESC im Query).
    """
    linked: set[str] = set()
    wmap: dict[str, dict[str, Any]] = {}
    for r in raw_rows:
        pr = _parse_apex_payload(r) or {}
        sid = _signal_id_from_apex_record(pr)
        if not sid:
            continue
        linked.add(sid)
        if sid not in wmap:
            wr = _war_room_from_record(pr)
            wmap[sid] = wr if isinstance(wr, dict) else {}
    return linked, wmap


def enrich_trade_evaluations_with_apex_war_room(
    conn: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fuegt consensus_penalty (0..1) und uncertainty_weight (>=1) pro Zeile hinzu,
    basierend auf Apex-Audit-Ledger (War-Room-JSON) und pnl_net_usdt.
    """
    sids: list[UUID] = []
    for row in rows:
        sid = row.get("signal_id")
        if sid is None:
            continue
        try:
            sids.append(UUID(str(sid)))
        except (TypeError, ValueError):
            continue
    ulist = list({s for s in sids})
    if not ulist:
        for row in rows:
            row["consensus_penalty"] = 0.0
            row["uncertainty_weight"] = 1.0
        return rows

    try:
        araw = _fetch_by_signal_json_path(conn, [str(s) for s in ulist])
    except (pg_errors.UndefinedTable, Exception) as exc:  # pragma: no cover — schema drift
        logger.info("enrich trade rows: apex_audit_ledger_entries %s", exc)
        for row in rows:
            row["consensus_penalty"] = 0.0
            row["uncertainty_weight"] = 1.0
        return rows

    linked, wmap = _index_war_room_by_signal(araw)
    for row in rows:
        sid = row.get("signal_id")
        if sid is None:
            row["consensus_penalty"] = 0.0
            row["uncertainty_weight"] = 1.0
            continue
        key = str(sid).lower()
        wr = wmap.get(key)
        has_link = key in linked
        try:
            pnl = float(row.get("pnl_net_usdt") or 0.0)
        except (TypeError, ValueError):
            pnl = 0.0
        cp, uw = consensus_to_labels(
            wr,
            pnl_net_usdt=pnl,
            has_signal_link=has_link,
        )
        row["consensus_penalty"] = cp
        row["uncertainty_weight"] = uw
    return rows
