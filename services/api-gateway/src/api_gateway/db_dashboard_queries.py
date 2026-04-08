"""SQL helpers for dashboard aggregation endpoints (Prompt 26)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors
from psycopg.types.json import Json

from api_gateway.db_live_queries import fetch_online_drift_state_row, normalize_tf_for_db
from api_gateway.signal_contract import (
    SIGNAL_API_CONTRACT_VERSION,
    build_explanation_layers,
    build_signal_view_detail,
    build_signal_view_list_item,
)


def _j(data: Any) -> Any:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    return data


def _risk_governor_from_signal_row(d: dict[str, Any]) -> dict[str, Any]:
    ss = _j(d.get("source_snapshot_json"))
    ss = ss if isinstance(ss, dict) else {}
    hd = ss.get("hybrid_decision")
    hd = hd if isinstance(hd, dict) else {}
    rg = hd.get("risk_governor")
    return dict(rg) if isinstance(rg, dict) else {}


def _parse_rg_json_list(raw: Any) -> list[Any]:
    parsed = _j(raw)
    return parsed if isinstance(parsed, list) else []


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "1", "yes", "y"}:
            return True
        if normalized in {"false", "f", "0", "no", "n"}:
            return False
    return None


def _instrument_metadata_entry(raw_meta: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    meta = _j(raw_meta)
    if not isinstance(meta, dict):
        return {}, None
    entry = meta.get("entry")
    if isinstance(entry, dict):
        merged = dict(entry)
        if meta.get("snapshot_id") not in (None, ""):
            merged.setdefault("snapshot_id", str(meta.get("snapshot_id")))
        if isinstance(meta.get("session_state"), dict):
            merged.setdefault("session_state", dict(meta.get("session_state")))
        if isinstance(meta.get("health_status"), str):
            merged.setdefault("health_status", meta.get("health_status"))
        if isinstance(meta.get("health_reasons"), list):
            merged.setdefault("health_reasons", list(meta.get("health_reasons")))
        return merged, meta
    return meta, meta


def _instrument_metadata_summary(
    raw_meta: Any,
    *,
    snapshot_id: Any = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    meta, raw_meta_dict = _instrument_metadata_entry(raw_meta)
    if not meta:
        return {"instrument_metadata": None} if include_raw else {}
    out: dict[str, Any] = {
        "instrument_metadata_snapshot_id": str(snapshot_id).strip()
        if snapshot_id not in (None, "")
        else (
            str(meta.get("snapshot_id")).strip()
            if meta.get("snapshot_id") not in (None, "")
            else None
        ),
        "instrument_venue": meta.get("venue")
        if isinstance(meta.get("venue"), str)
        else None,
        "instrument_category_key": meta.get("category_key")
        if isinstance(meta.get("category_key"), str)
        else None,
        "instrument_metadata_source": meta.get("metadata_source")
        if isinstance(meta.get("metadata_source"), str)
        else None,
        "instrument_metadata_verified": _coerce_bool(meta.get("metadata_verified")),
        "instrument_product_type": meta.get("product_type")
        if isinstance(meta.get("product_type"), str)
        else None,
        "instrument_margin_account_mode": meta.get("margin_account_mode")
        if isinstance(meta.get("margin_account_mode"), str)
        else None,
        "instrument_base_coin": meta.get("base_coin")
        if isinstance(meta.get("base_coin"), str)
        else None,
        "instrument_quote_coin": meta.get("quote_coin")
        if isinstance(meta.get("quote_coin"), str)
        else None,
        "instrument_settle_coin": meta.get("settle_coin")
        if isinstance(meta.get("settle_coin"), str)
        else None,
        "instrument_inventory_visible": _coerce_bool(meta.get("inventory_visible")),
        "instrument_analytics_eligible": _coerce_bool(meta.get("analytics_eligible")),
        "instrument_paper_shadow_eligible": _coerce_bool(meta.get("paper_shadow_eligible")),
        "instrument_live_execution_enabled": _coerce_bool(
            meta.get("live_execution_enabled")
        ),
        "instrument_execution_disabled": _coerce_bool(meta.get("execution_disabled")),
        "instrument_supports_funding": _coerce_bool(meta.get("supports_funding")),
        "instrument_supports_open_interest": _coerce_bool(meta.get("supports_open_interest")),
        "instrument_supports_long_short": _coerce_bool(meta.get("supports_long_short")),
        "instrument_supports_shorting": _coerce_bool(meta.get("supports_shorting")),
        "instrument_supports_reduce_only": _coerce_bool(meta.get("supports_reduce_only")),
        "instrument_supports_leverage": _coerce_bool(meta.get("supports_leverage")),
    }
    if include_raw:
        out["instrument_metadata"] = raw_meta_dict
    return out


def _shadow_live_from_execution_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("shadow_live_divergence")
    if not isinstance(raw, dict):
        return {
            "shadow_live_match_ok": None,
            "shadow_live_hard_violations": None,
            "shadow_live_soft_violations": None,
        }
    return {
        "shadow_live_match_ok": _coerce_bool(raw.get("match_ok")),
        "shadow_live_hard_violations": raw.get("hard_violations"),
        "shadow_live_soft_violations": raw.get("soft_violations"),
    }


def _latest_execution_status(
    *,
    execution_row: dict[str, Any] | None,
    alert_row: dict[str, Any] | None,
) -> dict[str, Any]:
    if execution_row is None:
        exec_payload: dict[str, Any] = {}
        shadow = {
            "shadow_live_match_ok": None,
            "shadow_live_hard_violations": None,
            "shadow_live_soft_violations": None,
        }
        execution_status = {
            "latest_execution_id": None,
            "latest_execution_decision_action": None,
            "latest_execution_decision_reason": None,
            "latest_execution_runtime_mode": None,
            "latest_execution_requested_mode": None,
            "latest_execution_created_ts": None,
            "operator_release_exists": False,
            "operator_release_source": None,
            "operator_release_ts": None,
            "live_mirror_eligible": None,
        }
    else:
        exec_payload = _j(execution_row.get("latest_execution_payload")) or {}
        exec_payload = exec_payload if isinstance(exec_payload, dict) else {}
        shadow = _shadow_live_from_execution_payload(exec_payload)
        execution_status = {
            "latest_execution_id": execution_row.get("latest_execution_id"),
            "latest_execution_decision_action": execution_row.get("latest_execution_decision_action"),
            "latest_execution_decision_reason": execution_row.get("latest_execution_decision_reason"),
            "latest_execution_runtime_mode": execution_row.get("latest_execution_runtime_mode"),
            "latest_execution_requested_mode": execution_row.get("latest_execution_requested_mode"),
            "latest_execution_created_ts": execution_row["latest_execution_created_ts"].isoformat()
            if execution_row.get("latest_execution_created_ts")
            else None,
            "operator_release_exists": bool(execution_row.get("operator_release_exists")),
            "operator_release_source": execution_row.get("operator_release_source"),
            "operator_release_ts": execution_row["operator_release_ts"].isoformat()
            if execution_row.get("operator_release_ts")
            else None,
            "live_mirror_eligible": _coerce_bool(exec_payload.get("live_mirror_eligible")),
        }
    if alert_row is None:
        telegram_status = {
            "telegram_alert_type": None,
            "telegram_delivery_state": None,
            "telegram_message_id": None,
            "telegram_sent_ts": None,
        }
    else:
        telegram_status = {
            "telegram_alert_type": alert_row.get("telegram_alert_type"),
            "telegram_delivery_state": alert_row.get("telegram_delivery_state"),
            "telegram_message_id": alert_row.get("telegram_message_id"),
            "telegram_sent_ts": alert_row["telegram_sent_ts"].isoformat()
            if alert_row.get("telegram_sent_ts")
            else None,
        }
    return {
        **execution_status,
        **shadow,
        **telegram_status,
    }


def _exit_router_from_reasons_json(reasons: Any) -> dict[str, Any]:
    rj = _j(reasons)
    if not isinstance(rj, dict):
        return {}
    dcf = rj.get("decision_control_flow")
    dcf = dcf if isinstance(dcf, dict) else {}
    edb = dcf.get("end_decision_binding")
    edb = edb if isinstance(edb, dict) else {}
    ex_eff = edb.get("exit_family_effective_primary")
    ex_ens = edb.get("exit_family_primary")
    spec = rj.get("specialists")
    spec = spec if isinstance(spec, dict) else {}
    ra = spec.get("router_arbitration")
    ra = ra if isinstance(ra, dict) else {}
    og = ra.get("operator_gate_required")
    return {
        "exit_family_effective_primary": ex_eff.strip() if isinstance(ex_eff, str) and ex_eff.strip() else None,
        "exit_family_primary_ensemble": ex_ens.strip() if isinstance(ex_ens, str) and ex_ens.strip() else None,
        "specialist_router_id": ra.get("router_id") if isinstance(ra.get("router_id"), str) else None,
        "router_selected_playbook_id": ra.get("selected_playbook_id")
        if isinstance(ra.get("selected_playbook_id"), str)
        else None,
        "router_operator_gate_required": bool(og) if isinstance(og, bool) else None,
    }


def _merge_exit_router(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    out = dict(primary)
    for k, v in fallback.items():
        if out.get(k) is None and v is not None:
            out[k] = v
    return out


def _exit_router_for_signal_row(d: dict[str, Any]) -> dict[str, Any]:
    base = _exit_router_from_reasons_json(d.get("reasons_json"))
    ss = _j(d.get("source_snapshot_json"))
    if isinstance(ss, dict):
        snap_rj: dict[str, Any] = {}
        if isinstance(ss.get("specialists"), dict):
            snap_rj["specialists"] = ss.get("specialists")
        if isinstance(ss.get("decision_control_flow"), dict):
            snap_rj["decision_control_flow"] = ss.get("decision_control_flow")
        if snap_rj:
            base = _merge_exit_router(base, _exit_router_from_reasons_json(snap_rj))
    return base


def fetch_signal_facets(
    conn: psycopg.Connection[Any],
    *,
    lookback_rows: int,
) -> dict[str, Any]:
    lim = max(100, min(20_000, int(lookback_rows)))
    mf = conn.execute(
        """
        SELECT DISTINCT market_family
        FROM (
            SELECT market_family FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE market_family IS NOT NULL AND market_family <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    pbf = conn.execute(
        """
        SELECT DISTINCT playbook_family
        FROM (
            SELECT playbook_family FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE playbook_family IS NOT NULL AND playbook_family <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    lanes = conn.execute(
        """
        SELECT DISTINCT meta_trade_lane
        FROM (
            SELECT meta_trade_lane FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE meta_trade_lane IS NOT NULL AND meta_trade_lane <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    sym = conn.execute(
        """
        SELECT DISTINCT symbol
        FROM (
            SELECT symbol FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    regimes = conn.execute(
        """
        SELECT DISTINCT regime_state
        FROM (
            SELECT regime_state FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE regime_state IS NOT NULL AND regime_state <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    routers = conn.execute(
        """
        SELECT DISTINCT specialist_router_id
        FROM (
            SELECT COALESCE(
                NULLIF(COALESCE(reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', ''),
                NULLIF(COALESCE(source_snapshot_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', '')
            ) AS specialist_router_id
            FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE specialist_router_id IS NOT NULL AND specialist_router_id <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    exits = conn.execute(
        """
        SELECT DISTINCT exit_family_effective_primary
        FROM (
            SELECT COALESCE(
                NULLIF(COALESCE(reasons_json, '{}'::jsonb)->'decision_control_flow'->'end_decision_binding'->>'exit_family_effective_primary', ''),
                NULLIF(COALESCE(source_snapshot_json, '{}'::jsonb)->'decision_control_flow'->'end_decision_binding'->>'exit_family_effective_primary', '')
            ) AS exit_family_effective_primary
            FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE exit_family_effective_primary IS NOT NULL AND exit_family_effective_primary <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    tfs = conn.execute(
        """
        SELECT DISTINCT timeframe
        FROM (
            SELECT timeframe FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE timeframe IS NOT NULL AND timeframe <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    dirs = conn.execute(
        """
        SELECT DISTINCT direction
        FROM (
            SELECT direction FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE direction IS NOT NULL AND direction <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    dstates = conn.execute(
        """
        SELECT DISTINCT decision_state
        FROM (
            SELECT decision_state FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE decision_state IS NOT NULL AND decision_state <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    tact = conn.execute(
        """
        SELECT DISTINCT trade_action
        FROM (
            SELECT trade_action FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE trade_action IS NOT NULL AND trade_action <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    strat = conn.execute(
        """
        SELECT DISTINCT strategy_name
        FROM (
            SELECT strategy_name FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE strategy_name IS NOT NULL AND strategy_name <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    pb_ids = conn.execute(
        """
        SELECT DISTINCT playbook_id
        FROM (
            SELECT playbook_id FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE playbook_id IS NOT NULL AND playbook_id <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    scls = conn.execute(
        """
        SELECT DISTINCT signal_class
        FROM (
            SELECT signal_class FROM app.signals_v1
            ORDER BY analysis_ts_ms DESC
            LIMIT %s
        ) t
        WHERE signal_class IS NOT NULL AND signal_class <> ''
        ORDER BY 1
        """,
        (lim,),
    ).fetchall()
    return {
        "lookback_rows": lim,
        "market_families": [str(dict(x)["market_family"]) for x in mf],
        "playbook_families": [str(dict(x)["playbook_family"]) for x in pbf],
        "meta_trade_lanes": [str(dict(x)["meta_trade_lane"]) for x in lanes],
        "regime_states": [str(dict(x)["regime_state"]) for x in regimes],
        "specialist_routers": [str(dict(x)["specialist_router_id"]) for x in routers],
        "exit_families": [str(dict(x)["exit_family_effective_primary"]) for x in exits],
        "symbols": [str(dict(x)["symbol"]) for x in sym],
        "timeframes": [str(dict(x)["timeframe"]) for x in tfs],
        "directions": [str(dict(x)["direction"]) for x in dirs],
        "decision_states": [str(dict(x)["decision_state"]) for x in dstates],
        "trade_actions": [str(dict(x)["trade_action"]) for x in tact],
        "strategy_names": [str(dict(x)["strategy_name"]) for x in strat],
        "playbook_ids": [str(dict(x)["playbook_id"]) for x in pb_ids],
        "signal_classes": [str(dict(x)["signal_class"]) for x in scls],
    }


def fetch_signals_recent(
    conn: psycopg.Connection[Any],
    *,
    symbol: str | None,
    timeframe: str | None,
    direction: str | None,
    min_strength: float | None,
    market_family: str | None,
    playbook_id: str | None,
    playbook_family: str | None,
    trade_action: str | None,
    meta_trade_lane: str | None,
    regime_state: str | None,
    specialist_router_id: str | None,
    exit_family: str | None,
    decision_state: str | None,
    strategy_name: str | None,
    signal_class: str | None,
    signal_registry_key: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    tf = normalize_tf_for_db(timeframe) if timeframe else None
    rows = conn.execute(
        """
        SELECT s.signal_id, s.symbol, s.timeframe, s.direction, s.market_regime,
               s.regime_bias, s.regime_confidence_0_1, s.signal_strength_0_100,
               s.probability_0_1, s.take_trade_prob, s.take_trade_model_version,
               s.take_trade_model_run_id, s.take_trade_calibration_method,
               s.expected_return_bps, s.expected_mae_bps, s.expected_mfe_bps,
               s.model_uncertainty_0_1, s.uncertainty_effective_for_leverage_0_1,
               s.model_ood_alert, s.trade_action,
               s.meta_decision_action, s.meta_decision_kernel_version,
               s.decision_confidence_0_1, s.decision_policy_version,
               s.allowed_leverage, s.recommended_leverage,
               s.leverage_policy_version, s.leverage_cap_reasons_json,
               s.signal_class, s.decision_state, s.analysis_ts_ms,
               s.created_at,
               s.meta_trade_lane, s.canonical_instrument_id, s.market_family,
               s.strategy_name, s.playbook_id, s.playbook_family, s.playbook_decision_mode,
               s.regime_state, s.regime_substate, s.regime_transition_state,
               s.stop_distance_pct, s.stop_budget_max_pct_allowed, s.stop_min_executable_pct,
               s.stop_fragility_0_1, s.stop_executability_0_1, s.stop_quality_0_1,
               s.stop_to_spread_ratio, s.stop_budget_policy_version,
               (COALESCE(s.source_snapshot_json, '{}'::jsonb)->>'instrument_metadata_snapshot_id')
                   AS instrument_metadata_snapshot_id,
               (COALESCE(s.source_snapshot_json, '{}'::jsonb)->'instrument_metadata')
                   AS instrument_metadata_raw,
               (s.source_snapshot_json->'hybrid_decision'->'risk_governor'
                    ->'live_execution_block_reasons_json') AS rg_live_blocks_raw,
               (s.source_snapshot_json->'hybrid_decision'->'risk_governor'
                    ->'universal_hard_block_reasons_json') AS rg_universal_blocks_raw,
               (s.reasons_json->'decision_control_flow'->'end_decision_binding'
                    ->>'exit_family_effective_primary') AS exit_family_effective_primary,
               (s.reasons_json->'decision_control_flow'->'end_decision_binding'
                    ->>'exit_family_primary') AS exit_family_primary_ensemble,
               (COALESCE(s.reasons_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'router_id') AS specialist_router_id_rj,
               (COALESCE(s.reasons_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'selected_playbook_id') AS router_playbook_id_rj,
               (COALESCE(s.reasons_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'operator_gate_required') AS router_operator_gate_rj,
               (COALESCE(s.source_snapshot_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'router_id') AS specialist_router_id_ss,
               (COALESCE(s.source_snapshot_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'selected_playbook_id') AS router_playbook_id_ss,
               (COALESCE(s.source_snapshot_json, '{}'::jsonb)->'specialists'
                    ->'router_arbitration'->>'operator_gate_required') AS router_operator_gate_ss,
               so.wins, so.losses, so.evaluations_count,
               lx.latest_execution_id,
               lx.latest_execution_decision_action,
               lx.latest_execution_decision_reason,
               lx.latest_execution_runtime_mode,
               lx.latest_execution_requested_mode,
               lx.latest_execution_created_ts,
               lx.latest_execution_payload,
               lx.operator_release_exists,
               lx.operator_release_source,
               lx.operator_release_ts,
               tg.telegram_alert_type,
               tg.telegram_delivery_state,
               tg.telegram_message_id,
               tg.telegram_sent_ts
        FROM app.signals_v1 s
        LEFT JOIN learn.signal_outcomes so ON so.signal_id = s.signal_id
        LEFT JOIN LATERAL (
            SELECT d.execution_id::text AS latest_execution_id,
                   d.decision_action AS latest_execution_decision_action,
                   d.decision_reason AS latest_execution_decision_reason,
                   d.effective_runtime_mode AS latest_execution_runtime_mode,
                   d.requested_runtime_mode AS latest_execution_requested_mode,
                   d.created_ts AS latest_execution_created_ts,
                   d.payload_json AS latest_execution_payload,
                   (rel.execution_id IS NOT NULL) AS operator_release_exists,
                   rel.source AS operator_release_source,
                   rel.released_ts AS operator_release_ts
            FROM live.execution_decisions d
            LEFT JOIN live.execution_operator_releases rel
              ON rel.execution_id = d.execution_id
            WHERE d.source_signal_id = s.signal_id::text
            ORDER BY d.created_ts DESC
            LIMIT 1
        ) lx ON true
        LEFT JOIN LATERAL (
            SELECT o.alert_type AS telegram_alert_type,
                   o.state AS telegram_delivery_state,
                   o.telegram_message_id,
                   o.sent_ts AS telegram_sent_ts
            FROM alert.alert_outbox o
            WHERE (o.payload->>'signal_id') = s.signal_id::text
               OR (
                    lx.latest_execution_id IS NOT NULL
                    AND (o.payload->>'execution_id') = lx.latest_execution_id
               )
            ORDER BY o.created_ts DESC
            LIMIT 1
        ) tg ON true
        WHERE (%(sym)s::text IS NULL OR s.symbol = %(sym)s)
          AND (%(tf)s::text IS NULL OR s.timeframe = %(tf)s)
          AND (%(dir)s::text IS NULL OR s.direction = %(dir)s)
          AND (%(min_st)s::numeric IS NULL OR s.signal_strength_0_100 >= %(min_st)s)
          AND (%(mf)s::text IS NULL OR s.market_family = %(mf)s)
          AND (%(pb)s::text IS NULL OR s.playbook_id = %(pb)s)
          AND (%(pbf)s::text IS NULL OR s.playbook_family = %(pbf)s)
          AND (%(ta)s::text IS NULL OR s.trade_action = %(ta)s)
          AND (%(lane)s::text IS NULL OR s.meta_trade_lane = %(lane)s)
          AND (%(rs)s::text IS NULL OR s.regime_state = %(rs)s)
          AND (
                %(router)s::text IS NULL
                OR COALESCE(
                    NULLIF(COALESCE(s.reasons_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', ''),
                    NULLIF(COALESCE(s.source_snapshot_json, '{}'::jsonb)->'specialists'->'router_arbitration'->>'router_id', '')
                ) = %(router)s
          )
          AND (
                %(exit_family)s::text IS NULL
                OR COALESCE(
                    NULLIF(COALESCE(s.reasons_json, '{}'::jsonb)->'decision_control_flow'->'end_decision_binding'->>'exit_family_effective_primary', ''),
                    NULLIF(COALESCE(s.source_snapshot_json, '{}'::jsonb)->'decision_control_flow'->'end_decision_binding'->>'exit_family_effective_primary', '')
                ) = %(exit_family)s
          )
          AND (%(decision_state)s::text IS NULL OR s.decision_state = %(decision_state)s)
          AND (%(strategy_name)s::text IS NULL OR s.strategy_name = %(strategy_name)s)
          AND (%(signal_class)s::text IS NULL OR s.signal_class = %(signal_class)s)
          AND (
                %(srk)s::text IS NULL
                OR (
                    NULLIF(TRIM(s.playbook_id), '') = %(srk)s
                    OR NULLIF(TRIM(s.strategy_name), '') = %(srk)s
                )
          )
        ORDER BY s.analysis_ts_ms DESC
        LIMIT %(lim)s
        """,
        {
            "sym": symbol.upper() if symbol else None,
            "tf": tf,
            "dir": direction.lower() if direction else None,
            "min_st": min_strength,
            "mf": market_family.strip() if market_family and market_family.strip() else None,
            "pb": playbook_id.strip() if playbook_id and playbook_id.strip() else None,
            "pbf": playbook_family.strip() if playbook_family and playbook_family.strip() else None,
            "ta": trade_action.strip().lower() if trade_action and trade_action.strip() else None,
            "lane": meta_trade_lane.strip() if meta_trade_lane and meta_trade_lane.strip() else None,
            "rs": regime_state.strip() if regime_state and regime_state.strip() else None,
            "router": specialist_router_id.strip()
            if specialist_router_id and specialist_router_id.strip()
            else None,
            "exit_family": exit_family.strip() if exit_family and exit_family.strip() else None,
            "decision_state": decision_state.strip()
            if decision_state and decision_state.strip()
            else None,
            "strategy_name": strategy_name.strip()
            if strategy_name and strategy_name.strip()
            else None,
            "signal_class": signal_class.strip()
            if signal_class and signal_class.strip()
            else None,
            "srk": signal_registry_key.strip()
            if signal_registry_key and signal_registry_key.strip()
            else None,
            "lim": limit,
        },
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ec = d.get("evaluations_count") or 0
        wins = d.get("wins") or 0
        losses = d.get("losses") or 0
        outcome_badge = None
        if ec and ec > 0:
            outcome_badge = {
                "evaluations_count": int(ec),
                "wins": int(wins),
                "losses": int(losses),
                "win_rate": float(wins) / float(ec),
            }
        live_blocks = _parse_rg_json_list(d.get("rg_live_blocks_raw"))
        uni_hard = _parse_rg_json_list(d.get("rg_universal_blocks_raw"))
        router_id = d.get("specialist_router_id_rj") or d.get("specialist_router_id_ss")
        router_pb = d.get("router_playbook_id_rj") or d.get("router_playbook_id_ss")
        og_raw = d.get("router_operator_gate_rj") if d.get("router_operator_gate_rj") is not None else d.get(
            "router_operator_gate_ss"
        )
        router_og = _coerce_bool(og_raw)
        ex_eff = d.get("exit_family_effective_primary")
        ex_eff_s = ex_eff.strip() if isinstance(ex_eff, str) else None
        ex_ens = d.get("exit_family_primary_ensemble")
        ex_ens_s = ex_ens.strip() if isinstance(ex_ens, str) else None
        instrument_meta = _instrument_metadata_summary(
            d.get("instrument_metadata_raw"),
            snapshot_id=d.get("instrument_metadata_snapshot_id"),
        )
        latest_status = _latest_execution_status(execution_row=d, alert_row=d)
        row_payload: dict[str, Any] = {
                "signal_id": str(d["signal_id"]),
                "symbol": d["symbol"],
                "timeframe": d["timeframe"],
                "direction": d["direction"],
                "market_regime": d.get("market_regime"),
                "regime_bias": d.get("regime_bias"),
                "regime_confidence_0_1": float(d["regime_confidence_0_1"])
                if d.get("regime_confidence_0_1") is not None
                else None,
                "signal_strength_0_100": float(d["signal_strength_0_100"]),
                "probability_0_1": float(d["probability_0_1"]),
                "take_trade_prob": float(d["take_trade_prob"])
                if d.get("take_trade_prob") is not None
                else None,
                "take_trade_model_version": d.get("take_trade_model_version"),
                "take_trade_model_run_id": str(d["take_trade_model_run_id"])
                if d.get("take_trade_model_run_id") is not None
                else None,
                "take_trade_calibration_method": d.get("take_trade_calibration_method"),
                "expected_return_bps": float(d["expected_return_bps"])
                if d.get("expected_return_bps") is not None
                else None,
                "expected_mae_bps": float(d["expected_mae_bps"])
                if d.get("expected_mae_bps") is not None
                else None,
                "expected_mfe_bps": float(d["expected_mfe_bps"])
                if d.get("expected_mfe_bps") is not None
                else None,
                "model_uncertainty_0_1": float(d["model_uncertainty_0_1"])
                if d.get("model_uncertainty_0_1") is not None
                else None,
                "uncertainty_effective_for_leverage_0_1": float(d["uncertainty_effective_for_leverage_0_1"])
                if d.get("uncertainty_effective_for_leverage_0_1") is not None
                else None,
                "model_ood_alert": bool(d.get("model_ood_alert")),
                "trade_action": d.get("trade_action"),
                "meta_decision_action": d.get("meta_decision_action"),
                "meta_decision_kernel_version": d.get("meta_decision_kernel_version"),
                "decision_confidence_0_1": float(d["decision_confidence_0_1"])
                if d.get("decision_confidence_0_1") is not None
                else None,
                "decision_policy_version": d.get("decision_policy_version"),
                "allowed_leverage": int(d["allowed_leverage"])
                if d.get("allowed_leverage") is not None
                else None,
                "recommended_leverage": int(d["recommended_leverage"])
                if d.get("recommended_leverage") is not None
                else None,
                "leverage_policy_version": d.get("leverage_policy_version"),
                "leverage_cap_reasons_json": _j(d.get("leverage_cap_reasons_json")) or [],
                "signal_class": d["signal_class"],
                "decision_state": d["decision_state"],
                "analysis_ts_ms": int(d["analysis_ts_ms"]),
                "created_ts": d["created_at"].isoformat() if d.get("created_at") else None,
                "outcome_badge": outcome_badge,
                "meta_trade_lane": d.get("meta_trade_lane"),
                "canonical_instrument_id": d.get("canonical_instrument_id"),
                "market_family": d.get("market_family"),
                "strategy_name": d.get("strategy_name"),
                "playbook_id": d.get("playbook_id"),
                "playbook_family": d.get("playbook_family"),
                "playbook_decision_mode": d.get("playbook_decision_mode"),
                "regime_state": d.get("regime_state"),
                "regime_substate": d.get("regime_substate"),
                "regime_transition_state": d.get("regime_transition_state"),
                "stop_distance_pct": float(d["stop_distance_pct"])
                if d.get("stop_distance_pct") is not None
                else None,
                "stop_budget_max_pct_allowed": float(d["stop_budget_max_pct_allowed"])
                if d.get("stop_budget_max_pct_allowed") is not None
                else None,
                "stop_min_executable_pct": float(d["stop_min_executable_pct"])
                if d.get("stop_min_executable_pct") is not None
                else None,
                "stop_fragility_0_1": float(d["stop_fragility_0_1"])
                if d.get("stop_fragility_0_1") is not None
                else None,
                "stop_executability_0_1": float(d["stop_executability_0_1"])
                if d.get("stop_executability_0_1") is not None
                else None,
                "stop_quality_0_1": float(d["stop_quality_0_1"])
                if d.get("stop_quality_0_1") is not None
                else None,
                "stop_to_spread_ratio": float(d["stop_to_spread_ratio"])
                if d.get("stop_to_spread_ratio") is not None
                else None,
                "stop_budget_policy_version": d.get("stop_budget_policy_version"),
                **instrument_meta,
                "exit_family_effective_primary": ex_eff_s,
                "exit_family_primary_ensemble": ex_ens_s,
                "specialist_router_id": router_id if isinstance(router_id, str) else None,
                "router_selected_playbook_id": router_pb if isinstance(router_pb, str) else None,
                "router_operator_gate_required": router_og,
                "live_execution_block_reasons_json": live_blocks,
                "governor_universal_hard_block_reasons_json": uni_hard,
                "live_execution_clear_for_real_money": len(live_blocks) == 0,
                **latest_status,
            }
        row_payload["signal_contract_version"] = SIGNAL_API_CONTRACT_VERSION
        row_payload["signal_view"] = build_signal_view_list_item(row_payload)
        out.append(row_payload)
    return out


def fetch_signal_by_id(conn: psycopg.Connection[Any], signal_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT s.*, so.wins, so.losses, so.evaluations_count
        FROM app.signals_v1 s
        LEFT JOIN learn.signal_outcomes so ON so.signal_id = s.signal_id
        WHERE s.signal_id = %s
        """,
        (str(signal_id),),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    ec = d.get("evaluations_count") or 0
    wins = d.get("wins") or 0
    outcome_badge = None
    if ec and ec > 0:
        outcome_badge = {
            "evaluations_count": int(ec),
            "wins": int(wins),
            "losses": int(d.get("losses") or 0),
            "win_rate": float(wins) / float(ec),
        }
    rg = _risk_governor_from_signal_row(d)
    live_blocks = rg.get("live_execution_block_reasons_json") or []
    live_blocks = live_blocks if isinstance(live_blocks, list) else []
    uni_hard = rg.get("universal_hard_block_reasons_json") or []
    uni_hard = uni_hard if isinstance(uni_hard, list) else []
    ex_rt = _exit_router_for_signal_row(d)
    source_snapshot = _j(d.get("source_snapshot_json"))
    source_snapshot = source_snapshot if isinstance(source_snapshot, dict) else {}
    instrument_meta = _instrument_metadata_summary(
        source_snapshot.get("instrument_metadata"),
        snapshot_id=source_snapshot.get("instrument_metadata_snapshot_id"),
        include_raw=True,
    )
    execution_row = conn.execute(
        """
        SELECT d.execution_id::text AS latest_execution_id,
               d.decision_action AS latest_execution_decision_action,
               d.decision_reason AS latest_execution_decision_reason,
               d.effective_runtime_mode AS latest_execution_runtime_mode,
               d.requested_runtime_mode AS latest_execution_requested_mode,
               d.created_ts AS latest_execution_created_ts,
               d.payload_json AS latest_execution_payload,
               (rel.execution_id IS NOT NULL) AS operator_release_exists,
               rel.source AS operator_release_source,
               rel.released_ts AS operator_release_ts
        FROM live.execution_decisions d
        LEFT JOIN live.execution_operator_releases rel
          ON rel.execution_id = d.execution_id
        WHERE d.source_signal_id = %s
        ORDER BY d.created_ts DESC
        LIMIT 1
        """,
        (str(signal_id),),
    ).fetchone()
    execution_data = dict(execution_row) if execution_row is not None else None
    latest_execution_id = execution_data.get("latest_execution_id") if execution_data else None
    alert_row = conn.execute(
        """
        SELECT o.alert_type AS telegram_alert_type,
               o.state AS telegram_delivery_state,
               o.telegram_message_id,
               o.sent_ts AS telegram_sent_ts
        FROM alert.alert_outbox o
        WHERE (o.payload->>'signal_id') = %s
           OR (%s::text IS NOT NULL AND (o.payload->>'execution_id') = %s)
        ORDER BY o.created_ts DESC
        LIMIT 1
        """,
        (str(signal_id), latest_execution_id, latest_execution_id),
    ).fetchone()
    latest_status = _latest_execution_status(
        execution_row=execution_data,
        alert_row=dict(alert_row) if alert_row is not None else None,
    )
    payload: dict[str, Any] = {
        "signal_id": str(d["signal_id"]),
        "symbol": d["symbol"],
        "timeframe": d["timeframe"],
        "direction": d["direction"],
        "canonical_instrument_id": d.get("canonical_instrument_id"),
        "market_family": d.get("market_family"),
        "strategy_name": d.get("strategy_name"),
        "playbook_id": d.get("playbook_id"),
        "playbook_family": d.get("playbook_family"),
        "playbook_decision_mode": d.get("playbook_decision_mode"),
        "meta_trade_lane": d.get("meta_trade_lane"),
        "regime_state": d.get("regime_state"),
        "regime_substate": d.get("regime_substate"),
        "regime_transition_state": d.get("regime_transition_state"),
        "stop_distance_pct": float(d["stop_distance_pct"])
        if d.get("stop_distance_pct") is not None
        else None,
        "stop_budget_max_pct_allowed": float(d["stop_budget_max_pct_allowed"])
        if d.get("stop_budget_max_pct_allowed") is not None
        else None,
        "stop_min_executable_pct": float(d["stop_min_executable_pct"])
        if d.get("stop_min_executable_pct") is not None
        else None,
        "stop_fragility_0_1": float(d["stop_fragility_0_1"])
        if d.get("stop_fragility_0_1") is not None
        else None,
        "stop_executability_0_1": float(d["stop_executability_0_1"])
        if d.get("stop_executability_0_1") is not None
        else None,
        "stop_quality_0_1": float(d["stop_quality_0_1"])
        if d.get("stop_quality_0_1") is not None
        else None,
        "stop_to_spread_ratio": float(d["stop_to_spread_ratio"])
        if d.get("stop_to_spread_ratio") is not None
        else None,
        "stop_budget_policy_version": d.get("stop_budget_policy_version"),
        **instrument_meta,
        "exit_family_effective_primary": ex_rt.get("exit_family_effective_primary"),
        "exit_family_primary_ensemble": ex_rt.get("exit_family_primary_ensemble"),
        "specialist_router_id": ex_rt.get("specialist_router_id"),
        "router_selected_playbook_id": ex_rt.get("router_selected_playbook_id"),
        "router_operator_gate_required": ex_rt.get("router_operator_gate_required"),
        "market_regime": d.get("market_regime"),
        "regime_bias": d.get("regime_bias"),
        "regime_confidence_0_1": float(d["regime_confidence_0_1"])
        if d.get("regime_confidence_0_1") is not None
        else None,
        "regime_reasons_json": d.get("regime_reasons_json") or [],
        "signal_strength_0_100": float(d["signal_strength_0_100"]),
        "probability_0_1": float(d["probability_0_1"]),
        "take_trade_prob": float(d["take_trade_prob"])
        if d.get("take_trade_prob") is not None
        else None,
        "take_trade_model_version": d.get("take_trade_model_version"),
        "take_trade_model_run_id": str(d["take_trade_model_run_id"])
        if d.get("take_trade_model_run_id") is not None
        else None,
        "take_trade_calibration_method": d.get("take_trade_calibration_method"),
        "expected_return_bps": float(d["expected_return_bps"])
        if d.get("expected_return_bps") is not None
        else None,
        "expected_mae_bps": float(d["expected_mae_bps"])
        if d.get("expected_mae_bps") is not None
        else None,
        "expected_mfe_bps": float(d["expected_mfe_bps"])
        if d.get("expected_mfe_bps") is not None
        else None,
        "target_projection_models_json": _j(d.get("target_projection_models_json")) or [],
        "model_uncertainty_0_1": float(d["model_uncertainty_0_1"])
        if d.get("model_uncertainty_0_1") is not None
        else None,
        "uncertainty_effective_for_leverage_0_1": float(
            d["uncertainty_effective_for_leverage_0_1"]
        )
        if d.get("uncertainty_effective_for_leverage_0_1") is not None
        else None,
        "shadow_divergence_0_1": float(d["shadow_divergence_0_1"])
        if d.get("shadow_divergence_0_1") is not None
        else None,
        "model_ood_score_0_1": float(d["model_ood_score_0_1"])
        if d.get("model_ood_score_0_1") is not None
        else None,
        "model_ood_alert": bool(d.get("model_ood_alert")),
        "uncertainty_reasons_json": _j(d.get("uncertainty_reasons_json")) or [],
        "ood_reasons_json": _j(d.get("ood_reasons_json")) or [],
        "abstention_reasons_json": _j(d.get("abstention_reasons_json")) or [],
        "trade_action": d.get("trade_action"),
        "meta_decision_action": d.get("meta_decision_action"),
        "meta_decision_kernel_version": d.get("meta_decision_kernel_version"),
        "decision_confidence_0_1": float(d["decision_confidence_0_1"])
        if d.get("decision_confidence_0_1") is not None
        else None,
        "decision_policy_version": d.get("decision_policy_version"),
        "allowed_leverage": int(d["allowed_leverage"])
        if d.get("allowed_leverage") is not None
        else None,
        "recommended_leverage": int(d["recommended_leverage"])
        if d.get("recommended_leverage") is not None
        else None,
        "leverage_policy_version": d.get("leverage_policy_version"),
        "leverage_cap_reasons_json": _j(d.get("leverage_cap_reasons_json")) or [],
        "signal_class": d["signal_class"],
        "decision_state": d["decision_state"],
        "rejection_state": d.get("rejection_state"),
        "rejection_reasons_json": d.get("rejection_reasons_json") or [],
        "analysis_ts_ms": int(d["analysis_ts_ms"]),
        "reasons_json": d.get("reasons_json") or [],
        "created_ts": d["created_at"].isoformat() if d.get("created_at") else None,
        "outcome_badge": outcome_badge,
        "live_execution_block_reasons_json": live_blocks,
        "governor_universal_hard_block_reasons_json": uni_hard,
        "portfolio_risk_synthesis_json": rg.get("portfolio_risk_synthesis_json"),
        "live_execution_clear_for_real_money": len(live_blocks) == 0,
        **latest_status,
    }
    payload["signal_contract_version"] = SIGNAL_API_CONTRACT_VERSION
    payload["signal_view"] = build_signal_view_detail(payload)
    return payload


def fetch_signal_explain(conn: psycopg.Connection[Any], signal_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT s.signal_id, e.explain_short, e.explain_long_md, e.risk_warnings_json,
               e.stop_explain_json, e.targets_explain_json, s.reasons_json
        FROM app.signals_v1 s
        LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
        WHERE s.signal_id = %s
        """,
        (str(signal_id),),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    rj = _j(d.get("reasons_json"))
    if rj is None:
        rj = []
    rw = _j(d.get("risk_warnings_json"))
    rw_list = rw if isinstance(rw, list) else []
    se = _j(d.get("stop_explain_json"))
    se_dict = se if isinstance(se, dict) else {}
    te = _j(d.get("targets_explain_json"))
    te_dict = te if isinstance(te, dict) else {}
    explain_short = d.get("explain_short")
    explain_long_md = d.get("explain_long_md")
    base: dict[str, Any] = {
        "signal_id": str(d["signal_id"]),
        "signal_contract_version": SIGNAL_API_CONTRACT_VERSION,
        "explain_short": explain_short,
        "explain_long_md": explain_long_md,
        "risk_warnings_json": rw_list,
        "stop_explain_json": se_dict,
        "targets_explain_json": te_dict,
        "reasons_json": rj,
    }
    base["explanation_layers"] = build_explanation_layers(
        explain_short=explain_short,
        explain_long_md=explain_long_md,
        risk_warnings_json=rw_list,
        stop_explain_json=se_dict,
        targets_explain_json=te_dict,
        reasons_json=rj,
    )
    return base


def fetch_paper_open_positions(
    conn: psycopg.Connection[Any], *, symbol: str | None
) -> list[dict[str, Any]]:
    if symbol:
        rows = conn.execute(
            """
            SELECT p.position_id, p.symbol, p.side, p.qty_base, p.entry_price_avg,
                   p.leverage, p.opened_ts_ms, p.updated_ts_ms, p.meta
            FROM paper.positions p
            WHERE p.state IN ('open', 'partially_closed')
              AND p.symbol = %s
            ORDER BY p.opened_ts_ms DESC
            """,
            (symbol.upper(),),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.position_id, p.symbol, p.side, p.qty_base, p.entry_price_avg,
                   p.leverage, p.opened_ts_ms, p.updated_ts_ms, p.meta
            FROM paper.positions p
            WHERE p.state IN ('open', 'partially_closed')
            ORDER BY p.opened_ts_ms DESC
            """
        ).fetchall()
    marks: dict[str, float] = {}
    if rows:
        syms = {str(dict(r)["symbol"]).upper() for r in rows}
        for s in syms:
            mr = conn.execute(
                """
                SELECT mark_price, last_pr FROM tsdb.ticker
                WHERE symbol = %s ORDER BY ts_ms DESC LIMIT 1
                """,
                (s,),
            ).fetchone()
            if mr:
                m = dict(mr)
                mp = m.get("mark_price") or m.get("last_pr")
                if mp is not None:
                    marks[s] = float(mp)
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        s = str(d["symbol"]).upper()
        mark = marks.get(s)
        qty = Decimal(str(d["qty_base"]))
        entry = Decimal(str(d["entry_price_avg"]))
        side = str(d["side"]).lower()
        u_pnl = Decimal("0")
        if mark is not None:
            m = Decimal(str(mark))
            u_pnl = (m - entry) * qty if side == "long" else (entry - m) * qty
        meta = _j(d.get("meta"))
        if not isinstance(meta, dict):
            meta = {}
        out.append(
            {
                "position_id": str(d["position_id"]),
                "symbol": d["symbol"],
                "side": d["side"],
                "qty_base": str(d["qty_base"]),
                "entry_price_avg": str(d["entry_price_avg"]),
                "mark_price": mark,
                "unrealized_pnl_usdt": float(u_pnl),
                "leverage": str(d["leverage"]),
                "leverage_allocator": meta.get("leverage_allocator")
                if isinstance(meta.get("leverage_allocator"), dict)
                else None,
                "opened_ts_ms": int(d["opened_ts_ms"]),
                "meta": meta,
            }
        )
    return out


def fetch_paper_trades_recent(
    conn: psycopg.Connection[Any], *, symbol: str | None, limit: int
) -> list[dict[str, Any]]:
    if symbol:
        rows = conn.execute(
            """
            SELECT p.position_id, p.symbol, p.side, p.qty_base, p.entry_price_avg,
                   p.closed_ts_ms, p.state, p.meta,
                   e.pnl_net_usdt, e.fees_total_usdt, e.funding_total_usdt,
                   e.direction_correct
            FROM paper.positions p
            LEFT JOIN learn.trade_evaluations e ON e.paper_trade_id = p.position_id
            WHERE p.state IN ('closed', 'liquidated') AND p.symbol = %s
            ORDER BY p.closed_ts_ms DESC NULLS LAST
            LIMIT %s
            """,
            (symbol.upper(), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.position_id, p.symbol, p.side, p.qty_base, p.entry_price_avg,
                   p.closed_ts_ms, p.state, p.meta,
                   e.pnl_net_usdt, e.fees_total_usdt, e.funding_total_usdt,
                   e.direction_correct
            FROM paper.positions p
            LEFT JOIN learn.trade_evaluations e ON e.paper_trade_id = p.position_id
            WHERE p.state IN ('closed', 'liquidated')
            ORDER BY p.closed_ts_ms DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        meta = _j(d.get("meta"))
        if not isinstance(meta, dict):
            meta = {}
        reason = meta.get("close_reason") or meta.get("reason_closed") or None
        out.append(
            {
                "position_id": str(d["position_id"]),
                "symbol": d["symbol"],
                "side": d["side"],
                "qty_base": str(d["qty_base"]),
                "entry_price_avg": str(d["entry_price_avg"]),
                "closed_ts_ms": int(d["closed_ts_ms"]) if d.get("closed_ts_ms") else None,
                "state": d["state"],
                "pnl_net_usdt": float(d["pnl_net_usdt"]) if d.get("pnl_net_usdt") is not None else None,
                "fees_total_usdt": float(d["fees_total_usdt"])
                if d.get("fees_total_usdt") is not None
                else None,
                "funding_total_usdt": float(d["funding_total_usdt"])
                if d.get("funding_total_usdt") is not None
                else None,
                "direction_correct": d.get("direction_correct"),
                "reason_closed": reason,
                "leverage_allocator": meta.get("leverage_allocator")
                if isinstance(meta.get("leverage_allocator"), dict)
                else None,
                "meta": {k: v for k, v in meta.items() if k not in ("close_reason", "reason_closed")},
            }
        )
    return out


def fetch_paper_metrics_summary(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    acc = conn.execute(
        """
        SELECT account_id, initial_equity, equity, currency
        FROM paper.accounts
        ORDER BY created_ts ASC
        LIMIT 1
        """
    ).fetchone()
    fee_sum = conn.execute("SELECT COALESCE(SUM(fee_usdt), 0) AS s FROM paper.fee_ledger").fetchone()
    fund_sum = conn.execute(
        "SELECT COALESCE(SUM(funding_usdt), 0) AS s FROM paper.funding_ledger"
    ).fetchone()
    acc_d: dict[str, Any] = {}
    if acc:
        a = dict(acc)
        acc_d = {
            "account_id": str(a["account_id"]),
            "initial_equity": float(a["initial_equity"]),
            "equity": float(a["equity"]),
            "currency": a.get("currency"),
        }
    fees = float(dict(fee_sum or {})["s"] or 0) if fee_sum else 0.0
    funding = float(dict(fund_sum or {})["s"] or 0) if fund_sum else 0.0
    return {
        "account": acc_d or None,
        "fees_total_usdt": fees,
        "funding_total_usdt": funding,
    }


def fetch_equity_series(conn: psycopg.Connection[Any], *, max_points: int) -> list[dict[str, Any]]:
    """Kumulative Equity aus learn.trade_evaluations; Startwert = initial_equity des ersten Paper-Kontos.

    Ohne Paper-Konto: leere Serie (keine erfundene 10k-Baseline — vermeidet Drift zur Summary).
    """
    acc = conn.execute(
        "SELECT initial_equity FROM paper.accounts ORDER BY created_ts ASC LIMIT 1"
    ).fetchone()
    if not acc:
        return []
    initial = float(dict(acc)["initial_equity"])
    rows = conn.execute(
        """
        SELECT closed_ts_ms, pnl_net_usdt
        FROM learn.trade_evaluations
        WHERE closed_ts_ms IS NOT NULL
        ORDER BY closed_ts_ms ASC
        LIMIT %s
        """,
        (max_points,),
    ).fetchall()
    cumulative = Decimal(str(initial))
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        cumulative += Decimal(str(d["pnl_net_usdt"]))
        out.append(
            {
                "time_s": int(d["closed_ts_ms"]) // 1000,
                "equity": float(cumulative),
            }
        )
    if not out:
        out.append({"time_s": int(__import__("time").time()), "equity": initial})
    return out


def fetch_news_scored(
    conn: psycopg.Connection[Any],
    *,
    min_score: int,
    sentiment: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    skip_sent = sentiment is None
    rows = conn.execute(
        """
        SELECT news_id, source, title, url, published_ts_ms, ingested_ts_ms,
               relevance_score, sentiment, impact_window, description,
               llm_summary_json
        FROM app.news_items
        WHERE relevance_score >= %s
          AND (%s OR sentiment = %s)
        ORDER BY COALESCE(published_ts_ms, ingested_ts_ms, 0) DESC
        LIMIT %s
        """,
        (min_score, skip_sent, sentiment or "", limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        llm = _j(d.get("llm_summary_json"))
        summary = d.get("description") or ""
        if isinstance(llm, dict) and llm.get("summary"):
            summary = str(llm["summary"])
        nid = d.get("news_id")
        out.append(
            {
                "news_id": str(nid) if nid else str(d.get("id", "")),
                "source": d.get("source"),
                "title": d.get("title"),
                "url": d.get("url"),
                "score_0_100": int(d["relevance_score"])
                if d.get("relevance_score") is not None
                else 0,
                "sentiment": d.get("sentiment"),
                "impact_window": d.get("impact_window"),
                "published_ts_ms": int(d["published_ts_ms"])
                if d.get("published_ts_ms") is not None
                else None,
                "summary": (summary or "")[:500],
            }
        )
    return out


def fetch_news_by_id(conn: psycopg.Connection[Any], news_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT news_id, id as legacy_id, source, title, url, published_ts_ms, ingested_ts_ms,
               relevance_score, sentiment, impact_window, description, content, llm_summary_json
        FROM app.news_items
        WHERE news_id = %s
        LIMIT 1
        """,
        (str(news_id),),
    ).fetchone()
    if row is None:
        row = conn.execute(
            """
            SELECT news_id, id as legacy_id, source, title, url, published_ts_ms, ingested_ts_ms,
                   relevance_score, sentiment, impact_window, description, content, llm_summary_json
            FROM app.news_items
            WHERE id::text = %s
            LIMIT 1
            """,
            (str(news_id),),
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    llm = _j(d.get("llm_summary_json"))
    return {
        "news_id": str(d.get("news_id") or d.get("legacy_id")),
        "source": d.get("source"),
        "title": d.get("title"),
        "url": d.get("url"),
        "score_0_100": int(d["relevance_score"]) if d.get("relevance_score") is not None else 0,
        "sentiment": d.get("sentiment"),
        "impact_window": d.get("impact_window"),
        "published_ts_ms": int(d["published_ts_ms"]) if d.get("published_ts_ms") else None,
        "description": d.get("description"),
        "content": d.get("content"),
        "llm_summary_json": llm if isinstance(llm, dict) else {},
    }


def fetch_signal_aggregate_by_strategy_names(
    conn: psycopg.Connection[Any], names: list[str]
) -> dict[str, dict[str, Any]]:
    """Signale zaehlen, bei denen playbook_id ODER strategy_name dem Registry-Namen entspricht.

    (Nicht COALESCE pro Zeile — sonst wuerde eine Zeile mit playbook_id=A, strategy_name=B
    nur unter A fallen und B-Registry-Zuordnungen verfehlen.)
    """
    if not names:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT
                n.nm AS k,
                COUNT(s.signal_id)::bigint AS signal_count,
                MAX(s.analysis_ts_ms) AS last_signal_ts_ms
            FROM unnest(%s::text[]) AS n(nm)
            LEFT JOIN app.signals_v1 s
              ON (
                NULLIF(TRIM(s.playbook_id), '') = n.nm
                OR NULLIF(TRIM(s.strategy_name), '') = n.nm
              )
            GROUP BY n.nm
            """,
            (names,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        k = d.get("k")
        if not k:
            continue
        out[str(k)] = {
            "signal_count": int(d["signal_count"] or 0),
            "last_signal_ts_ms": int(d["last_signal_ts_ms"])
            if d.get("last_signal_ts_ms") is not None
            else None,
        }
    return out


def fetch_signal_path_playbooks_unlinked(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    """
    Playbook-/Strategie-Keys aus dem Signalpfad ohne passende Zeile in learn.strategies (name).
    Verhindert den Eindruck einer leeren Registry, obwohl Signale bereits Playbook-IDs tragen.
    """
    try:
        rows = conn.execute(
            """
            WITH agg AS (
                SELECT
                    COALESCE(
                        NULLIF(TRIM(playbook_id), ''),
                        NULLIF(TRIM(strategy_name), '')
                    ) AS playbook_key,
                    MAX(playbook_family) FILTER (WHERE playbook_family IS NOT NULL) AS playbook_family,
                    COUNT(*)::bigint AS signal_count,
                    MAX(analysis_ts_ms) AS last_signal_ts_ms
                FROM app.signals_v1
                WHERE COALESCE(
                    NULLIF(TRIM(playbook_id), ''),
                    NULLIF(TRIM(strategy_name), '')
                ) IS NOT NULL
                GROUP BY 1
            )
            SELECT a.playbook_key, a.playbook_family, a.signal_count, a.last_signal_ts_ms,
                   s.strategy_id::text AS linked_strategy_id
            FROM agg a
            LEFT JOIN learn.strategies s ON s.name = a.playbook_key
            WHERE s.strategy_id IS NULL
            ORDER BY a.signal_count DESC, a.playbook_key ASC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ts_ms = d.get("last_signal_ts_ms")
        out.append(
            {
                "playbook_key": d["playbook_key"],
                "playbook_family": d.get("playbook_family"),
                "signal_count": int(d["signal_count"] or 0),
                "last_signal_ts_ms": int(ts_ms) if ts_ms is not None else None,
                "registry_row_kind": "signal_path_only",
            }
        )
    return out


def fetch_strategies_registry(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.strategy_id, s.name, s.description, s.scope_json, s.created_ts,
               st.current_status,
               sv.version AS latest_version,
               scr.metrics_json AS rolling_metrics
        FROM learn.strategies s
        LEFT JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
        LEFT JOIN LATERAL (
            SELECT version FROM learn.strategy_versions
            WHERE strategy_id = s.strategy_id
            ORDER BY created_ts DESC LIMIT 1
        ) sv ON true
        LEFT JOIN learn.strategy_scores_rolling scr
          ON scr.strategy_id = s.strategy_id AND scr.time_window = '30d'
        ORDER BY s.updated_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    names = [str(dict(r)["name"]) for r in rows]
    sig_map = fetch_signal_aggregate_by_strategy_names(conn, names)
    for r in rows:
        d = dict(r)
        mj = d.get("rolling_metrics") or {}
        if isinstance(mj, str):
            mj = _j(mj)
        if not isinstance(mj, dict):
            mj = {}
        raw_status = d.get("current_status")
        lifecycle = raw_status if raw_status else "not_set"
        nm = str(d["name"])
        sig = sig_map.get(nm) or {"signal_count": 0, "last_signal_ts_ms": None}
        rolling_row = d.get("rolling_metrics")
        rolling_snapshot_empty = rolling_row is None
        out.append(
            {
                "strategy_id": str(d["strategy_id"]),
                "name": nm,
                "description": d.get("description"),
                "status": lifecycle,
                "latest_version": d.get("latest_version"),
                "scope_json": d.get("scope_json") or {},
                "rolling_pf": mj.get("profit_factor") or mj.get("pf"),
                "rolling_win_rate": mj.get("win_rate") or mj.get("winRate"),
                "rolling_metrics_json": mj,
                "rolling_time_window": "30d",
                "rolling_snapshot_empty": rolling_snapshot_empty,
                "created_ts": d["created_ts"].isoformat() if d.get("created_ts") else None,
                "registry_row_kind": "registry",
                "signal_path_signal_count": sig["signal_count"],
                "signal_path_last_signal_ts_ms": sig["last_signal_ts_ms"],
            }
        )
    return out


def fetch_strategy_detail(conn: psycopg.Connection[Any], strategy_id: UUID) -> dict[str, Any] | None:
    strat = conn.execute(
        """
        SELECT strategy_id, name, description, scope_json, created_ts, updated_ts
        FROM learn.strategies WHERE strategy_id = %s
        """,
        (str(strategy_id),),
    ).fetchone()
    if strat is None:
        return None
    s = dict(strat)
    versions = conn.execute(
        """
        SELECT strategy_version_id, version, created_ts
        FROM learn.strategy_versions
        WHERE strategy_id = %s
        ORDER BY created_ts DESC
        """,
        (str(strategy_id),),
    ).fetchall()
    hist = conn.execute(
        """
        SELECT old_status, new_status, reason, changed_by, ts
        FROM learn.strategy_status_history
        WHERE strategy_id = %s
        ORDER BY ts DESC
        LIMIT 50
        """,
        (str(strategy_id),),
    ).fetchall()
    st = conn.execute(
        "SELECT current_status, updated_ts FROM learn.strategy_status WHERE strategy_id = %s",
        (str(strategy_id),),
    ).fetchone()
    st_d = dict(st) if st else {}
    try:
        rolling_rows = conn.execute(
            """
            SELECT time_window, metrics_json, updated_ts
            FROM learn.strategy_scores_rolling
            WHERE strategy_id = %s
            ORDER BY time_window ASC
            """,
            (str(strategy_id),),
        ).fetchall()
    except pg_errors.UndefinedTable:
        rolling_rows = []
    performance_rolling: list[dict[str, Any]] = []
    for rr in rolling_rows:
        rd = dict(rr)
        mj = rd.get("metrics_json") or {}
        if isinstance(mj, str):
            mj = _j(mj)
        if not isinstance(mj, dict):
            mj = {}
        performance_rolling.append(
            {
                "time_window": rd.get("time_window"),
                "metrics_json": mj,
                "updated_ts": rd["updated_ts"].isoformat() if rd.get("updated_ts") else None,
            }
        )
    nm = str(s["name"])
    sig_map = fetch_signal_aggregate_by_strategy_names(conn, [nm])
    sig = sig_map.get(nm) or {"signal_count": 0, "last_signal_ts_ms": None}
    cs = st_d.get("current_status")
    perf_empty = len(performance_rolling) == 0
    return {
        "strategy_id": str(s["strategy_id"]),
        "name": nm,
        "description": s.get("description"),
        "scope_json": s.get("scope_json") or {},
        "created_ts": s["created_ts"].isoformat() if s.get("created_ts") else None,
        "updated_ts": s["updated_ts"].isoformat() if s.get("updated_ts") else None,
        "current_status": cs,
        "lifecycle_status": cs if cs else "not_set",
        "performance_rolling_empty": perf_empty,
        "performance_rolling_empty_hint_de": (
            "Keine Zeilen in learn.strategy_scores_rolling fuer diese Strategie — "
            "keine Laufzeit-Performance aus dem Registry-Fenster. "
            "Das ist kein Signalfehler; Auswertungen erscheinen, wenn die Learning-Pipeline schreibt."
            if perf_empty
            else None
        ),
        "status_updated_ts": st_d["updated_ts"].isoformat() if st_d.get("updated_ts") else None,
        "versions": [
            {
                "strategy_version_id": str(dict(v)["strategy_version_id"]),
                "version": dict(v)["version"],
                "created_ts": dict(v)["created_ts"].isoformat() if dict(v).get("created_ts") else None,
            }
            for v in versions
        ],
        "status_history": [
            {
                "old_status": dict(h).get("old_status"),
                "new_status": dict(h)["new_status"],
                "reason": dict(h).get("reason"),
                "changed_by": dict(h).get("changed_by"),
                "ts": dict(h)["ts"].isoformat() if dict(h).get("ts") else None,
            }
            for h in hist
        ],
        "performance_rolling": performance_rolling,
        "signal_path": {
            "registry_key": nm,
            "matching_signal_count": sig["signal_count"],
            "last_signal_ts_ms": sig["last_signal_ts_ms"],
            "signals_list_query_param": "signal_registry_key",
            "match_rule_de": (
                "Zaehlung aller app.signals_v1-Zeilen, bei denen TRIM(playbook_id) oder "
                "TRIM(strategy_name) exakt learn.strategies.name entspricht (ODER-Verknuepfung pro Zeile)."
            ),
            "signals_link_hint_de": (
                "Signalseite mit ?signal_registry_key=<name> — gleiche Logik wie diese Zaehlung; "
                "reines ?playbook_id= filtert nur die Spalte playbook_id."
            ),
        },
        "ai_explanations": {
            "availability": "none",
            "hint_de": (
                "Strategie-spezifische KI-Erklaerungen (Operator-Explain, Signal-Explain) sind "
                "nicht Teil der Registry-Antwort. Nutze die Signalseite und LLM-Operator-Pfade "
                "fuer kontextbezogene Texte."
            ),
        },
    }


def fetch_strategy_status_row(
    conn: psycopg.Connection[Any], strategy_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT s.strategy_id, s.name, st.current_status, st.updated_ts
        FROM learn.strategies s
        LEFT JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
        WHERE s.strategy_id = %s
        """,
        (str(strategy_id),),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    cs = d.get("current_status")
    return {
        "strategy_id": str(d["strategy_id"]),
        "name": d["name"],
        "current_status": cs,
        "lifecycle_status": cs if cs else "not_set",
        "updated_ts": d["updated_ts"].isoformat() if d.get("updated_ts") else None,
    }


def fetch_model_registry_v2_slots(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT g.model_name, g.role, g.run_id::text AS run_id, g.calibration_status,
               g.activated_ts, g.notes, g.updated_ts, g.scope_type, g.scope_key,
               r.version, r.promoted_bool, r.calibration_method
        FROM app.model_registry_v2 g
        JOIN app.model_runs r ON r.run_id = g.run_id AND r.model_name = g.model_name
        ORDER BY g.model_name ASC, g.scope_type ASC, g.scope_key ASC, g.role ASC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        out.append(
            {
                "model_name": d["model_name"],
                "role": d["role"],
                "run_id": d["run_id"],
                "calibration_status": d["calibration_status"],
                "activated_ts": d["activated_ts"].isoformat() if d.get("activated_ts") else None,
                "notes": d.get("notes"),
                "updated_ts": d["updated_ts"].isoformat() if d.get("updated_ts") else None,
                "version": d.get("version"),
                "promoted_bool": bool(d.get("promoted_bool")),
                "calibration_method": d.get("calibration_method"),
                "scope_type": d.get("scope_type") or "global",
                "scope_key": d.get("scope_key") if d.get("scope_key") is not None else "",
            }
        )
    return out


def fetch_learning_strategy_metrics(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.strategy_id, s.name, m.time_window AS window, m.metrics_json, m.updated_ts
        FROM learn.strategy_metrics m
        JOIN learn.strategies s ON s.strategy_id = m.strategy_id
        ORDER BY m.updated_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "strategy_id": str(dict(r)["strategy_id"]),
            "strategy_name": dict(r)["name"],
            "window": dict(r)["window"],
            "metrics_json": dict(r).get("metrics_json") or {},
            "updated_ts": dict(r)["updated_ts"].isoformat() if dict(r).get("updated_ts") else None,
        }
        for r in rows
    ]


def fetch_error_patterns_top(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pattern_key, time_window AS window, count, examples_json, updated_ts
        FROM learn.error_patterns
        ORDER BY count DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "pattern_key": dict(r)["pattern_key"],
            "window": dict(r)["window"],
            "count": int(dict(r)["count"]),
            "examples_json": dict(r).get("examples_json") or [],
            "updated_ts": dict(r)["updated_ts"].isoformat() if dict(r).get("updated_ts") else None,
        }
        for r in rows
    ]


def fetch_recommendations_recent(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT rec_id, type, payload_json, status, created_ts
        FROM learn.recommendations
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "rec_id": str(dict(r)["rec_id"]),
            "type": dict(r)["type"],
            "payload_json": dict(r).get("payload_json") or {},
            "status": dict(r)["status"],
            "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
        }
        for r in rows
    ]


def fetch_model_ops_report(conn: psycopg.Connection[Any], *, slice_hours: int = 168) -> dict[str, Any]:
    """
    Aggregiert Kalibrierungs-/Drift-/Slice-/Abstentions-Kennzahlen fuer Operator-Dashboard (read-only).
    """
    hours = max(1, min(int(slice_hours), 24 * 90))
    online = fetch_online_drift_state_row(conn)
    drift_n = conn.execute(
        """
        SELECT COUNT(*)::bigint AS c
        FROM learn.drift_events
        WHERE detected_ts >= now() - interval '24 hours'
        """
    ).fetchone()
    champ = conn.execute(
        """
        SELECT r.run_id, r.version,
               r.metrics_json -> 'calibration_curve' AS calibration_curve,
               r.metrics_json -> 'cv_summary' AS cv_summary,
               r.metrics_json -> 'brier_score' AS brier_score
        FROM app.model_registry_v2 g
        INNER JOIN app.model_runs r
            ON r.run_id = g.run_id AND r.model_name = g.model_name
        WHERE g.model_name = 'take_trade_prob' AND g.role = 'champion'
          AND g.scope_type = 'global' AND (g.scope_key IS NULL OR g.scope_key = '')
        LIMIT 1
        """
    ).fetchone()
    regime_rows = conn.execute(
        """
        SELECT COALESCE(market_regime, 'unknown') AS slice_key, COUNT(*)::bigint AS n
        FROM app.signals_v1
        WHERE created_at >= now() - (%s::int * interval '1 hour')
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 40
        """,
        (hours,),
    ).fetchall()
    family_rows = conn.execute(
        """
        SELECT
            COALESCE(
                NULLIF(TRIM(source_snapshot_json ->> 'market_family'), ''),
                NULLIF(TRIM(source_snapshot_json #>> '{instrument,market_family}'), ''),
                'unknown'
            ) AS slice_key,
            COUNT(*)::bigint AS n
        FROM app.signals_v1
        WHERE created_at >= now() - (%s::int * interval '1 hour')
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 40
        """,
        (hours,),
    ).fetchall()
    abst_row = conn.execute(
        """
        SELECT
            COUNT(*)::bigint AS n_total,
            COUNT(*) FILTER (WHERE trade_action = 'do_not_trade')::bigint AS n_do_not_trade,
            COUNT(*) FILTER (WHERE trade_action IS DISTINCT FROM 'do_not_trade' AND trade_action IS NOT NULL)::bigint AS n_other_action,
            COUNT(*) FILTER (
                WHERE trade_action = 'do_not_trade' AND COALESCE(model_ood_alert, false)
            )::bigint AS n_abstain_with_ood_alert
        FROM app.signals_v1
        WHERE created_at >= now() - (%s::int * interval '1 hour')
        """,
        (hours,),
    ).fetchone()
    abst = dict(abst_row) if abst_row else {}
    n_abst = int(abst.get("n_do_not_trade") or 0)
    n_ood_al = int(abst.get("n_abstain_with_ood_alert") or 0)
    return {
        "schema_version": "model-ops-report-v1",
        "slice_hours": hours,
        "online_drift": online,
        "drift_events_last_24h": int(dict(drift_n or {}).get("c") or 0) if drift_n else 0,
        "champion_take_trade_snapshot": (
            {
                "run_id": str(dict(champ)["run_id"]),
                "version": dict(champ).get("version"),
                "brier_score": dict(champ).get("brier_score"),
                "has_calibration_curve": dict(champ).get("calibration_curve") is not None,
                "cv_summary": dict(champ).get("cv_summary"),
            }
            if champ
            else None
        ),
        "signal_slices": {
            "by_market_regime": [
                {"slice_key": dict(r)["slice_key"], "count": int(dict(r)["n"])} for r in regime_rows
            ],
            "by_market_family_in_snapshot": [
                {"slice_key": dict(r)["slice_key"], "count": int(dict(r)["n"])} for r in family_rows
            ],
        },
        "abstention_and_no_trade": {
            "n_signals": int(abst.get("n_total") or 0),
            "n_do_not_trade": n_abst,
            "n_other_trade_action": int(abst.get("n_other_action") or 0),
            "abstain_with_ood_alert_fraction": (n_ood_al / n_abst) if n_abst else None,
            "note_de": "ood_alert_fraction ist Proxy fuer Abstention-Ausrichtung, keine echte Forward-Precision ohne Labels.",
        },
    }


def fetch_drift_recent(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT drift_id, metric_name, severity, details_json, detected_ts
            FROM learn.drift_events
            ORDER BY detected_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    return [
        {
            "drift_id": str(dict(r)["drift_id"]),
            "metric_name": dict(r)["metric_name"],
            "severity": dict(r)["severity"],
            "details_json": dict(r).get("details_json") or {},
            "detected_ts": dict(r)["detected_ts"].isoformat() if dict(r).get("detected_ts") else None,
        }
        for r in rows
    ]


def fetch_backtest_runs(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT run_id, symbol, status, cv_method, metrics_json, created_ts, mode
        FROM learn.backtest_runs
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "run_id": str(dict(r)["run_id"]),
            "symbol": dict(r).get("symbol"),
            "mode": dict(r).get("mode"),
            "status": dict(r).get("status"),
            "cv_method": dict(r).get("cv_method"),
            "metrics_json": dict(r).get("metrics_json") or {},
            "created_ts": dict(r)["created_ts"].isoformat() if dict(r).get("created_ts") else None,
        }
        for r in rows
    ]


def fetch_admin_rules(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT rule_set_id, rules_json, updated_ts FROM app.admin_rules ORDER BY rule_set_id"
    ).fetchall()
    return [
        {
            "rule_set_id": dict(r)["rule_set_id"],
            "rules_json": dict(r)["rules_json"] or {},
            "updated_ts": dict(r)["updated_ts"].isoformat() if dict(r).get("updated_ts") else None,
        }
        for r in rows
    ]


def upsert_admin_rules(
    conn: psycopg.Connection[Any], *, rule_set_id: str, rules_json: dict[str, Any]
) -> None:
    conn.execute(
        """
        INSERT INTO app.admin_rules (rule_set_id, rules_json, updated_ts)
        VALUES (%s, %s, now())
        ON CONFLICT (rule_set_id) DO UPDATE SET
          rules_json = EXCLUDED.rules_json,
          updated_ts = now()
        """,
        (rule_set_id, Json(rules_json)),
    )


def update_strategy_status(
    conn: psycopg.Connection[Any],
    *,
    strategy_id: UUID,
    new_status: str,
    reason: str | None,
    changed_by: str,
) -> bool:
    exists = conn.execute(
        "SELECT 1 FROM learn.strategies WHERE strategy_id = %s",
        (str(strategy_id),),
    ).fetchone()
    if exists is None:
        return False
    cur = conn.execute(
        "SELECT current_status FROM learn.strategy_status WHERE strategy_id = %s",
        (str(strategy_id),),
    ).fetchone()
    if cur is None:
        conn.execute(
            """
            INSERT INTO learn.strategy_status (strategy_id, current_status, updated_ts)
            VALUES (%s, %s, now())
            """,
            (str(strategy_id), new_status),
        )
        old = None
    else:
        old = dict(cur).get("current_status")
        conn.execute(
            """
            UPDATE learn.strategy_status
            SET current_status = %s, updated_ts = now()
            WHERE strategy_id = %s
            """,
            (new_status, str(strategy_id)),
        )
    conn.execute(
        """
        INSERT INTO learn.strategy_status_history
          (strategy_id, old_status, new_status, reason, changed_by, ts)
        VALUES (%s, %s, %s, %s, %s, now())
        """,
        (str(strategy_id), old, new_status, reason, changed_by),
    )
    return True


def fetch_data_freshness(conn: psycopg.Connection[Any], *, symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    c = conn.execute(
        """
        SELECT MAX(start_ts_ms) AS ts FROM tsdb.candles WHERE symbol = %s
        """,
        (sym,),
    ).fetchone()
    sig = conn.execute(
        "SELECT MAX(analysis_ts_ms) AS ts FROM app.signals_v1 WHERE symbol = %s", (sym,)
    ).fetchone()
    news = conn.execute(
        "SELECT MAX(COALESCE(published_ts_ms, ingested_ts_ms, 0)) AS ts FROM app.news_items"
    ).fetchone()
    return {
        "last_candle_ts_ms": int(dict(c)["ts"]) if c and dict(c).get("ts") is not None else None,
        "last_signal_ts_ms": int(dict(sig)["ts"]) if sig and dict(sig).get("ts") is not None else None,
        "last_news_ts_ms": int(dict(news)["ts"]) if news and dict(news).get("ts") is not None else None,
    }
