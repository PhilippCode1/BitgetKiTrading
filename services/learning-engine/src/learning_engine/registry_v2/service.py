from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import psycopg
from fastapi import HTTPException
from psycopg import errors as pg_errors

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2.champion_promotion_gates import evaluate_champion_promotion_gates
from learning_engine.storage import (
    repo_model_champion_lifecycle,
    repo_model_runs,
    repo_model_registry_v2,
    repo_online_drift,
)
from shared_py.model_registry_policy import (
    champion_assignment_calibration_ok,
    model_requires_probability_calibration,
)
from shared_py.model_registry_scope import normalize_registry_scope

logger = logging.getLogger("learning_engine.registry_v2")

_OVERRIDE_REASON_MIN_LEN = 8


def _audit(conn: psycopg.Connection[Any], *, action: str, entity_id: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO app.audit_log (entity_schema, entity_table, entity_id, action, payload)
        VALUES ('app', 'model_registry_v2', %s, %s, %s::jsonb)
        """,
        (entity_id, action, json.dumps(payload, default=str)),
    )


def assign_champion(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    model_name: str,
    run_id: UUID,
    notes: str | None = None,
    changed_by: str = "api",
    promotion_manual_override: bool = False,
    promotion_override_reason: str | None = None,
    skip_promotion_gates: bool = False,
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    st, sk = normalize_registry_scope(scope_type=scope_type, scope_key=scope_key)
    row = repo_model_registry_v2.fetch_model_run_by_id(conn, run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="model_run nicht gefunden")
    if str(row.get("model_name") or "") != model_name:
        raise HTTPException(status_code=400, detail="run_id passt nicht zu model_name")

    if not champion_assignment_calibration_ok(
        model_name=model_name,
        calibration_required=settings.model_calibration_required,
        calibration_method=row.get("calibration_method"),
        metadata_json=row.get("metadata_json"),
    ):
        raise HTTPException(
            status_code=400,
            detail="Kalibrierungspflicht nicht erfuellt (MODEL_CALIBRATION_REQUIRED=true)",
        )

    gate_report: dict[str, Any] = {"skipped_gates": skip_promotion_gates}
    if not skip_promotion_gates:
        od_eff: str | None = None
        if settings.model_promotion_apply_online_drift_gate and st == "global" and sk == "":
            od_row = repo_online_drift.fetch_online_drift_state(conn, scope="global")
            if od_row:
                od_eff = str(od_row.get("effective_action") or "ok")
        gr = evaluate_champion_promotion_gates(
            model_name=model_name,
            metrics_json=row.get("metrics_json"),
            metadata_json=row.get("metadata_json"),
            settings=settings,
            online_drift_effective_action=od_eff,
            promotion_scope_type=st,
            promotion_scope_key=sk,
        )
        gate_report = {"ok": gr.ok, "reasons": list(gr.reasons), "details": gr.details}
        if not gr.ok:
            reason_txt = (promotion_override_reason or "").strip()
            allow_override = (
                promotion_manual_override
                and settings.model_promotion_manual_override_enabled
                and len(reason_txt) >= _OVERRIDE_REASON_MIN_LEN
            )
            if not allow_override:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "promotion_gates_failed",
                        "reasons": list(gr.reasons),
                        "details": gr.details,
                        "hint": "Mit promotion_manual_override=true und ausreichend promotion_override_reason "
                        "oder MODEL_PROMOTION_GATES_ENABLED=false / Gates anpassen.",
                    },
                )
            gate_report["manual_override"] = True
            gate_report["override_reason"] = reason_txt
            gate_report["changed_by"] = changed_by

    cal_status = (
        "verified"
        if model_requires_probability_calibration(model_name)
        else "not_applicable"
    )

    _close_champion_history_safe(
        conn,
        model_name=model_name,
        ended_reason="superseded_by_new_champion",
        scope_type=st,
        scope_key=sk,
    )

    if st == "global" and sk == "":
        repo_model_runs.clear_promoted_model(conn, model_name=model_name)
        conn.execute(
            "UPDATE app.model_runs SET promoted_bool = true WHERE run_id = %s",
            (str(run_id),),
        )

    slot = repo_model_registry_v2.upsert_registry_slot(
        conn,
        model_name=model_name,
        role="champion",
        run_id=run_id,
        calibration_status=cal_status,
        notes=notes,
        scope_type=st,
        scope_key=sk,
    )
    _insert_champion_history_safe(
        conn,
        model_name=model_name,
        run_id=run_id,
        changed_by=changed_by,
        promotion_gate_report=gate_report,
        scope_type=st,
        scope_key=sk,
    )

    entity_id = f"{model_name}:champion:{st}:{sk}"
    _audit(
        conn,
        action="champion_assigned",
        entity_id=entity_id,
        payload={
            "run_id": str(run_id),
            "calibration_status": cal_status,
            "changed_by": changed_by,
            "promotion_gate_report": gate_report,
            "scope_type": st,
            "scope_key": sk,
        },
    )
    logger.info(
        "registry_v2 champion model=%s run_id=%s scope=%s:%s",
        model_name,
        run_id,
        st,
        sk,
    )
    return {"status": "ok", "slot": slot, "promotion_gate_report": gate_report}


def assign_challenger(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    model_name: str,
    run_id: UUID,
    notes: str | None = None,
    changed_by: str = "api",
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    st, sk = normalize_registry_scope(scope_type=scope_type, scope_key=scope_key)
    row = repo_model_registry_v2.fetch_model_run_by_id(conn, run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="model_run nicht gefunden")
    if str(row.get("model_name") or "") != model_name:
        raise HTTPException(status_code=400, detail="run_id passt nicht zu model_name")

    if not champion_assignment_calibration_ok(
        model_name=model_name,
        calibration_required=settings.model_calibration_required,
        calibration_method=row.get("calibration_method"),
        metadata_json=row.get("metadata_json"),
    ):
        raise HTTPException(
            status_code=400,
            detail="Kalibrierungspflicht nicht erfuellt (MODEL_CALIBRATION_REQUIRED=true)",
        )

    cal_status = (
        "verified"
        if model_requires_probability_calibration(model_name)
        else "not_applicable"
    )
    slot = repo_model_registry_v2.upsert_registry_slot(
        conn,
        model_name=model_name,
        role="challenger",
        run_id=run_id,
        calibration_status=cal_status,
        notes=notes,
        scope_type=st,
        scope_key=sk,
    )
    entity_id = f"{model_name}:challenger:{st}:{sk}"
    _audit(
        conn,
        action="challenger_assigned",
        entity_id=entity_id,
        payload={
            "run_id": str(run_id),
            "changed_by": changed_by,
            "scope_type": st,
            "scope_key": sk,
        },
    )
    logger.info(
        "registry_v2 challenger model=%s run_id=%s scope=%s:%s",
        model_name,
        run_id,
        st,
        sk,
    )
    return {"status": "ok", "slot": slot}


def clear_registry_slot(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    role: str,
    changed_by: str = "api",
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    if role not in ("champion", "challenger"):
        raise HTTPException(status_code=400, detail="role muss champion oder challenger sein")
    st, sk = normalize_registry_scope(scope_type=scope_type, scope_key=scope_key)
    if role == "champion":
        _close_champion_history_safe(
            conn,
            model_name=model_name,
            ended_reason="champion_slot_cleared",
            scope_type=st,
            scope_key=sk,
        )
    ok = repo_model_registry_v2.delete_slot(
        conn, model_name=model_name, role=role, scope_type=st, scope_key=sk
    )
    if role == "champion" and ok and st == "global" and sk == "":
        repo_model_runs.clear_promoted_model(conn, model_name=model_name)
    entity_id = f"{model_name}:{role}:{st}:{sk}"
    _audit(
        conn,
        action=f"{role}_cleared",
        entity_id=entity_id,
        payload={"changed_by": changed_by, "scope_type": st, "scope_key": sk},
    )
    return {"status": "ok", "deleted": ok}


def list_registry_snapshot(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    items = repo_model_registry_v2.list_registry_with_runs(conn)
    return {
        "status": "ok",
        "items": [repo_model_runs.jsonable_row(x) for x in items],
    }


def _close_champion_history_safe(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    ended_reason: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> None:
    try:
        repo_model_champion_lifecycle.close_open_champion_history(
            conn,
            model_name=model_name,
            ended_reason=ended_reason,
            scope_type=scope_type,
            scope_key=scope_key,
        )
    except pg_errors.UndefinedTable:
        logger.warning("model_champion_history fehlt — Migration 410 ausfuehren")
    except pg_errors.UndefinedColumn:
        logger.warning("model_champion_history.scope_* fehlt — Migration 550 ausfuehren")


def _insert_champion_history_safe(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    run_id: UUID,
    changed_by: str,
    promotion_gate_report: dict[str, Any],
    scope_type: str = "global",
    scope_key: str = "",
) -> None:
    try:
        repo_model_champion_lifecycle.insert_champion_history_open(
            conn,
            model_name=model_name,
            run_id=run_id,
            changed_by=changed_by,
            promotion_gate_report=promotion_gate_report,
            scope_type=scope_type,
            scope_key=scope_key,
        )
    except pg_errors.UndefinedTable:
        logger.warning("model_champion_history fehlt — Migration 410 ausfuehren")
    except pg_errors.UndefinedColumn:
        logger.warning("model_champion_history.scope_* fehlt — Migration 550 ausfuehren")


def mark_stable_champion_checkpoint(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    run_id: UUID | None,
    marked_by: str,
    notes: str | None = None,
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    st, sk = normalize_registry_scope(scope_type=scope_type, scope_key=scope_key)
    target = run_id
    if target is None:
        cur = repo_model_champion_lifecycle.fetch_registry_slot_run_id(
            conn, model_name=model_name, role="champion", scope_type=st, scope_key=sk
        )
        if cur is None:
            raise HTTPException(status_code=404, detail="kein Champion-Slot fuer model_name/scope")
        target = cur
    slot = repo_model_champion_lifecycle.fetch_registry_slot_run_id(
        conn, model_name=model_name, role="champion", scope_type=st, scope_key=sk
    )
    if slot is None or slot != target:
        raise HTTPException(
            status_code=400,
            detail="run_id muss aktueller Champion sein (oder run_id weglassen fuer aktuellen)",
        )
    try:
        repo_model_champion_lifecycle.upsert_stable_checkpoint(
            conn,
            model_name=model_name,
            run_id=target,
            marked_by=marked_by,
            notes=notes,
            scope_type=st,
            scope_key=sk,
        )
    except pg_errors.UndefinedTable as exc:
        raise HTTPException(
            status_code=503,
            detail="app.model_stable_champion_checkpoint fehlt — Migration 410/550",
        ) from exc
    entity_id = f"{model_name}:stable_checkpoint:{st}:{sk}"
    _audit(
        conn,
        action="stable_champion_checkpoint_marked",
        entity_id=entity_id,
        payload={"run_id": str(target), "marked_by": marked_by, "scope_type": st, "scope_key": sk},
    )
    return {
        "status": "ok",
        "model_name": model_name,
        "run_id": str(target),
        "scope_type": st,
        "scope_key": sk,
    }


def rollback_champion_to_stable_checkpoint(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    model_name: str,
    changed_by: str,
    reason: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    st, sk = normalize_registry_scope(scope_type=scope_type, scope_key=scope_key)
    rid = repo_model_champion_lifecycle.fetch_stable_checkpoint_run_id(
        conn, model_name=model_name, scope_type=st, scope_key=sk
    )
    if rid is None:
        raise HTTPException(
            status_code=404,
            detail="kein stabiler Checkpoint — zuerst POST .../stable-checkpoint",
        )
    cur = repo_model_champion_lifecycle.fetch_registry_slot_run_id(
        conn, model_name=model_name, role="champion", scope_type=st, scope_key=sk
    )
    if cur == rid:
        return {
            "status": "ok",
            "noop": True,
            "detail": "Champion entspricht bereits Checkpoint",
            "run_id": str(rid),
            "scope_type": st,
            "scope_key": sk,
        }
    notes = f"rollback_stable:{reason[:500]}"
    out = assign_champion(
        conn,
        settings,
        model_name=model_name,
        run_id=rid,
        notes=notes,
        changed_by=changed_by,
        skip_promotion_gates=True,
        scope_type=st,
        scope_key=sk,
    )
    entity_id = f"{model_name}:champion:{st}:{sk}"
    _audit(
        conn,
        action="champion_rollback_stable",
        entity_id=entity_id,
        payload={
            "run_id": str(rid),
            "changed_by": changed_by,
            "reason": reason[:500],
            "scope_type": st,
            "scope_key": sk,
        },
    )
    return {**out, "rollback": True, "scope_type": st, "scope_key": sk}


def try_auto_rollback_on_drift_hard_block(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    previous_effective_action: str,
    new_effective_action: str,
) -> dict[str, Any] | None:
    if not settings.model_registry_auto_rollback_on_drift_hard_block:
        return None
    if new_effective_action != "hard_block" or previous_effective_action == "hard_block":
        return None
    mn = (settings.model_registry_auto_rollback_model_name or "").strip()
    if not mn:
        return None
    rid = repo_model_champion_lifecycle.fetch_stable_checkpoint_run_id(
        conn, model_name=mn, scope_type="global", scope_key=""
    )
    if rid is None:
        logger.warning(
            "auto_rollback skipped: no stable checkpoint for model_name=%s (global)",
            mn,
        )
        return {"attempted": True, "applied": False, "detail": "no_stable_checkpoint"}
    try:
        out = rollback_champion_to_stable_checkpoint(
            conn,
            settings,
            model_name=mn,
            changed_by="online_drift_auto",
            reason="effective_action_escalated_to_hard_block",
            scope_type="global",
            scope_key="",
        )
        return {"attempted": True, "applied": not out.get("noop"), "result": out}
    except HTTPException as exc:
        logger.warning("auto_rollback failed: %s", exc.detail)
        return {"attempted": True, "applied": False, "detail": str(exc.detail)}
