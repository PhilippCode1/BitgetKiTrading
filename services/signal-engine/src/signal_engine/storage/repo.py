from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from signal_engine.config import TIMEFRAMES_ORDER


class SignalRepository:
    def __init__(
        self,
        database_url: str,
        *,
        logger: logging.Logger | None = None,
        model_registry_v2_enabled: bool = False,
        model_calibration_required: bool = False,
        model_champion_name: str = "take_trade_prob",
        model_registry_scoped_slots_enabled: bool = False,
    ) -> None:
        self._database_url = database_url
        self._logger = logger or logging.getLogger("signal_engine.repo")
        self._model_registry_v2_enabled = model_registry_v2_enabled
        self._model_calibration_required = model_calibration_required
        self._model_champion_name = (model_champion_name or "").strip()
        self._model_registry_scoped_slots_enabled = model_registry_scoped_slots_enabled

    def fetch_structure_state(
        self, *, symbol: str, timeframe: str, max_ts_ms: int
    ) -> dict[str, Any] | None:
        sql = """
        SELECT * FROM app.structure_state
        WHERE symbol = %s AND timeframe = ANY(%s)
          AND last_ts_ms <= %s
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, _timeframe_aliases(timeframe), max_ts_ms)).fetchone()
        if row is None:
            return None
        out = dict(row)
        if isinstance(out.get("breakout_box_json"), str):
            out["breakout_box_json"] = json.loads(out["breakout_box_json"])
        return out

    def fetch_structure_events(
        self, *, symbol: str, timeframe: str, max_ts_ms: int, limit: int = 40
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT event_id::text AS event_id, type, ts_ms, details_json
        FROM app.structure_events
        WHERE symbol = %s AND timeframe = ANY(%s)
          AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(
                sql,
                (symbol, _timeframe_aliases(timeframe), max_ts_ms, limit),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("details_json"), str):
                d["details_json"] = json.loads(d["details_json"])
            out.append(d)
        return out

    def fetch_latest_feature(
        self,
        *,
        symbol: str,
        timeframe: str,
        max_start_ts_ms: int,
        canonical_instrument_id: str | None = None,
        market_family: str | None = None,
    ) -> dict[str, Any] | None:
        filters = ["timeframe = ANY(%s)", "start_ts_ms <= %s"]
        params: list[object] = [_timeframe_aliases(timeframe), max_start_ts_ms]
        if canonical_instrument_id:
            filters.insert(0, "canonical_instrument_id = %s")
            params.insert(0, canonical_instrument_id)
        else:
            filters.insert(0, "symbol = %s")
            params.insert(0, symbol)
        if market_family:
            filters.append("market_family = %s")
            params.append(market_family)
        sql = f"""
        SELECT * FROM features.candle_features
        WHERE {" AND ".join(filters)}
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetch_features_by_timeframes(
        self,
        *,
        symbol: str,
        timeframes: tuple[str, ...],
        max_start_ts_ms: int,
        canonical_instrument_id: str | None = None,
        market_family: str | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        result: dict[str, dict[str, Any] | None] = {tf: None for tf in timeframes}
        for tf in timeframes:
            result[tf] = self.fetch_latest_feature(
                symbol=symbol,
                timeframe=tf,
                max_start_ts_ms=max_start_ts_ms,
                canonical_instrument_id=canonical_instrument_id,
                market_family=market_family,
            )
        return result

    def fetch_previous_regime_snapshot(
        self,
        *,
        symbol: str,
        timeframe: str,
        max_analysis_ts_ms: int,
        canonical_instrument_id: str | None = None,
        market_family: str | None = None,
    ) -> dict[str, Any] | None:
        filters = ["timeframe = %s", "analysis_ts_ms < %s"]
        params: list[object] = [timeframe, max_analysis_ts_ms]
        if canonical_instrument_id:
            filters.insert(0, "canonical_instrument_id = %s")
            params.insert(0, canonical_instrument_id)
        else:
            filters.insert(0, "symbol = %s")
            params.insert(0, symbol)
        if market_family:
            filters.append("market_family = %s")
            params.append(market_family)
        sql = f"""
        SELECT market_regime, regime_state, regime_substate, regime_transition_state,
               regime_transition_reasons_json, regime_persistence_bars,
               source_snapshot_json, analysis_ts_ms
        FROM app.signals_v1
        WHERE {" AND ".join(filters)}
        ORDER BY analysis_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        out = dict(row)
        if isinstance(out.get("regime_transition_reasons_json"), str):
            out["regime_transition_reasons_json"] = json.loads(out["regime_transition_reasons_json"])
        source_snapshot = out.get("source_snapshot_json")
        if isinstance(source_snapshot, str):
            try:
                source_snapshot = json.loads(source_snapshot)
            except json.JSONDecodeError:
                source_snapshot = {}
        if isinstance(source_snapshot, dict):
            regime_snapshot = source_snapshot.get("regime_snapshot")
            if isinstance(regime_snapshot, dict):
                out["source_regime_snapshot"] = regime_snapshot
        return out

    def fetch_latest_close(
        self,
        *,
        symbol: str,
        timeframe: str,
        max_start_ts_ms: int,
    ) -> float | None:
        sql = """
        SELECT close FROM tsdb.candles
        WHERE symbol = %s AND timeframe = ANY(%s)
          AND start_ts_ms <= %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(
                sql,
                (symbol, _timeframe_aliases(timeframe), max_start_ts_ms),
            ).fetchone()
        if row is None:
            return None
        return float(row["close"])

    def fetch_active_drawings(
        self,
        *,
        symbol: str,
        timeframe: str,
        max_ts_ms: int,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT DISTINCT ON (parent_id)
            drawing_id, parent_id, revision, symbol, timeframe, type, status,
            geometry_json, style_json, reasons_json, confidence,
            (EXTRACT(EPOCH FROM created_ts) * 1000)::bigint AS created_ts_ms,
            (EXTRACT(EPOCH FROM updated_ts) * 1000)::bigint AS updated_ts_ms
        FROM app.drawings
        WHERE symbol = %s AND timeframe = ANY(%s) AND status = 'active'
          AND (EXTRACT(EPOCH FROM updated_ts) * 1000)::bigint <= %s
        ORDER BY parent_id, revision DESC
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(
                sql,
                (symbol, _timeframe_aliases(timeframe), max_ts_ms),
            ).fetchall()
        return [_drawing_row_to_dict(dict(r)) for r in rows]

    def fetch_latest_news(self, *, symbol: str, max_ts_ms: int) -> dict[str, Any] | None:
        sql_symbol = """
        SELECT id, relevance_score, sentiment, impact_window, title, published_ts, news_id,
               published_ts_ms, scored_ts_ms, ingested_ts_ms, source
        FROM app.news_items
        WHERE COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) <= %s
          AND (
                title ILIKE %s
             OR description ILIKE %s
             OR content ILIKE %s
             OR entities_json::text ILIKE %s
             OR raw_json::text ILIKE %s
          )
        ORDER BY
          CASE LOWER(TRIM(source))
            WHEN 'cryptopanic' THEN 1
            WHEN 'coindesk' THEN 2
            WHEN 'newsapi' THEN 3
            WHEN 'gdelt' THEN 4
            ELSE 5
          END ASC,
          COALESCE(relevance_score, -1) DESC,
          COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) DESC,
          id DESC
        LIMIT 1
        """
        sql_fallback = """
        SELECT id, relevance_score, sentiment, impact_window, title, published_ts, news_id,
               published_ts_ms, scored_ts_ms, ingested_ts_ms, source
        FROM app.news_items
        WHERE COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) <= %s
        ORDER BY
          CASE LOWER(TRIM(source))
            WHEN 'cryptopanic' THEN 1
            WHEN 'coindesk' THEN 2
            WHEN 'newsapi' THEN 3
            WHEN 'gdelt' THEN 4
            ELSE 5
          END ASC,
          COALESCE(relevance_score, -1) DESC,
          COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) DESC,
          id DESC
        LIMIT 1
        """
        sym = symbol.upper()
        like = f"%{sym}%"
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(
                sql_symbol,
                (max_ts_ms, like, like, like, like, like),
            ).fetchone()
            if row is None:
                row = conn.execute(sql_fallback, (max_ts_ms,)).fetchone()
        return dict(row) if row else None

    def fetch_prior_signal_stats(
        self, *, symbol: str, timeframe: str, limit: int = 12
    ) -> tuple[int, float | None]:
        sql_total = """
        SELECT COUNT(*) AS c FROM app.signals_v1
        WHERE symbol = %s AND timeframe = %s
        """
        sql_recent = """
        SELECT weighted_composite_score_0_100 AS s
        FROM app.signals_v1
        WHERE symbol = %s AND timeframe = %s
        ORDER BY analysis_ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            total = int(conn.execute(sql_total, (symbol, timeframe)).fetchone()["c"])
            rows = conn.execute(sql_recent, (symbol, timeframe, limit)).fetchall()
        if not rows:
            return total, None
        vals = [float(r["s"]) for r in rows]
        return total, sum(vals) / len(vals)

    def insert_signal_v1(self, row: dict[str, Any]) -> None:
        sql = """
        INSERT INTO app.signals_v1 (
            signal_id, canonical_instrument_id, symbol, market_family, timeframe, analysis_ts_ms, market_regime,
            regime_bias, regime_confidence_0_1, regime_reasons_json,
            regime_state, regime_substate, regime_transition_state, regime_transition_reasons_json,
            regime_persistence_bars, regime_policy_version,
            direction, signal_strength_0_100, probability_0_1,
            take_trade_prob, take_trade_model_version, take_trade_model_run_id,
            take_trade_calibration_method,
            expected_return_bps, expected_mae_bps, expected_mfe_bps, target_projection_models_json,
            model_uncertainty_0_1, uncertainty_effective_for_leverage_0_1,
            shadow_divergence_0_1, model_ood_score_0_1, model_ood_alert,
            uncertainty_reasons_json, ood_reasons_json, abstention_reasons_json, trade_action,
            meta_decision_action, meta_decision_kernel_version, meta_decision_bundle_json,
            operator_override_audit_json,
            meta_trade_lane,
            decision_confidence_0_1, decision_policy_version, allowed_leverage, recommended_leverage,
            leverage_policy_version, leverage_cap_reasons_json,
            signal_class,
            structure_score_0_100, momentum_score_0_100, multi_timeframe_score_0_100,
            news_score_0_100, risk_score_0_100, history_score_0_100,
            weighted_composite_score_0_100,
            rejection_state, rejection_reasons_json, decision_state, reasons_json,
            supporting_drawing_ids_json, supporting_structure_event_ids_json,
            stop_zone_id, target_zone_ids_json, reward_risk_ratio,
            expected_volatility_band, source_snapshot_json, scoring_model_version,
            strategy_name, playbook_id, playbook_family, playbook_decision_mode,
            playbook_registry_version,
            stop_distance_pct, stop_budget_max_pct_allowed, stop_min_executable_pct,
            stop_to_spread_ratio, stop_quality_0_1, stop_executability_0_1, stop_fragility_0_1,
            stop_budget_policy_version,
            signal_components_history_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, %s::jsonb,
            %s,
            %s, %s, %s::jsonb, %s::jsonb,
            %s,
            %s, %s, %s, %s, %s,
            %s::jsonb,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s::jsonb,
            %s, %s::jsonb,
            %s::jsonb, %s::jsonb, %s, %s::jsonb,
            %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s::jsonb
        )
        """
        comp_hist = row.get("signal_components_history_json")
        comp_hist_json = (
            json.dumps(comp_hist, separators=(",", ":")) if comp_hist is not None else None
        )
        params = (
            row["signal_id"],
            row.get("canonical_instrument_id"),
            row["symbol"],
            row.get("market_family"),
            row["timeframe"],
            row["analysis_ts_ms"],
            row.get("market_regime"),
            row.get("regime_bias"),
            None
            if row.get("regime_confidence_0_1") is None
            else str(row["regime_confidence_0_1"]),
            json.dumps(row.get("regime_reasons_json") or [], separators=(",", ":")),
            row.get("regime_state"),
            row.get("regime_substate"),
            row.get("regime_transition_state"),
            json.dumps(row.get("regime_transition_reasons_json") or [], separators=(",", ":")),
            row.get("regime_persistence_bars"),
            row.get("regime_policy_version"),
            row["direction"],
            str(row["signal_strength_0_100"]),
            str(row["probability_0_1"]),
            None if row.get("take_trade_prob") is None else str(row["take_trade_prob"]),
            row.get("take_trade_model_version"),
            row.get("take_trade_model_run_id"),
            row.get("take_trade_calibration_method"),
            None if row.get("expected_return_bps") is None else str(row["expected_return_bps"]),
            None if row.get("expected_mae_bps") is None else str(row["expected_mae_bps"]),
            None if row.get("expected_mfe_bps") is None else str(row["expected_mfe_bps"]),
            json.dumps(row.get("target_projection_models_json") or [], separators=(",", ":")),
            None
            if row.get("model_uncertainty_0_1") is None
            else str(row["model_uncertainty_0_1"]),
            None
            if row.get("uncertainty_effective_for_leverage_0_1") is None
            else str(row["uncertainty_effective_for_leverage_0_1"]),
            None
            if row.get("shadow_divergence_0_1") is None
            else str(row["shadow_divergence_0_1"]),
            None if row.get("model_ood_score_0_1") is None else str(row["model_ood_score_0_1"]),
            bool(row.get("model_ood_alert")),
            json.dumps(row.get("uncertainty_reasons_json") or [], separators=(",", ":")),
            json.dumps(row.get("ood_reasons_json") or [], separators=(",", ":")),
            json.dumps(row.get("abstention_reasons_json") or [], separators=(",", ":")),
            row.get("trade_action"),
            row.get("meta_decision_action"),
            row.get("meta_decision_kernel_version"),
            json.dumps(row.get("meta_decision_bundle_json") or {}, separators=(",", ":")),
            None
            if row.get("operator_override_audit_json") is None
            else json.dumps(row.get("operator_override_audit_json"), separators=(",", ":")),
            row.get("meta_trade_lane"),
            None
            if row.get("decision_confidence_0_1") is None
            else str(row["decision_confidence_0_1"]),
            row.get("decision_policy_version"),
            row.get("allowed_leverage"),
            row.get("recommended_leverage"),
            row.get("leverage_policy_version"),
            json.dumps(row.get("leverage_cap_reasons_json") or [], separators=(",", ":")),
            row["signal_class"],
            str(row["structure_score_0_100"]),
            str(row["momentum_score_0_100"]),
            str(row["multi_timeframe_score_0_100"]),
            str(row["news_score_0_100"]),
            str(row["risk_score_0_100"]),
            str(row["history_score_0_100"]),
            str(row["weighted_composite_score_0_100"]),
            row["rejection_state"],
            json.dumps(row["rejection_reasons_json"], separators=(",", ":")),
            row["decision_state"],
            json.dumps(row["reasons_json"], separators=(",", ":")),
            json.dumps(row["supporting_drawing_ids_json"], separators=(",", ":")),
            json.dumps(row["supporting_structure_event_ids_json"], separators=(",", ":")),
            row.get("stop_zone_id"),
            json.dumps(row["target_zone_ids_json"], separators=(",", ":")),
            None if row.get("reward_risk_ratio") is None else str(row["reward_risk_ratio"]),
            None
            if row.get("expected_volatility_band") is None
            else str(row["expected_volatility_band"]),
            json.dumps(row["source_snapshot_json"], separators=(",", ":")),
            row["scoring_model_version"],
            row.get("strategy_name"),
            row.get("playbook_id"),
            row.get("playbook_family"),
            row.get("playbook_decision_mode"),
            row.get("playbook_registry_version"),
            None if row.get("stop_distance_pct") is None else str(row["stop_distance_pct"]),
            None
            if row.get("stop_budget_max_pct_allowed") is None
            else str(row["stop_budget_max_pct_allowed"]),
            None if row.get("stop_min_executable_pct") is None else str(row["stop_min_executable_pct"]),
            None if row.get("stop_to_spread_ratio") is None else str(row["stop_to_spread_ratio"]),
            None if row.get("stop_quality_0_1") is None else str(row["stop_quality_0_1"]),
            None
            if row.get("stop_executability_0_1") is None
            else str(row["stop_executability_0_1"]),
            None if row.get("stop_fragility_0_1") is None else str(row["stop_fragility_0_1"]),
            row.get("stop_budget_policy_version"),
            comp_hist_json,
        )
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(sql, params)

    def fetch_latest_promoted_model_run(self, *, model_name: str) -> dict[str, Any] | None:
        """Legacy: nur promoted_bool. Produktion nutzt fetch_production_model_run."""
        sql = """
        SELECT run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
               artifact_path, target_name, output_field, calibration_method, metadata_json,
               created_ts
        FROM app.model_runs
        WHERE model_name = %s AND promoted_bool = true
        ORDER BY created_ts DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (model_name,)).fetchone()
        return dict(row) if row else None

    def fetch_production_model_run(
        self,
        *,
        model_name: str,
        market_family: str | None = None,
        market_regime: str | None = None,
        playbook_id: str | None = None,
        router_slot: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, Any] | None:
        from shared_py.model_registry_policy import production_probability_calibration_satisfied
        from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME

        if (
            model_name == TAKE_TRADE_MODEL_NAME
            and self._model_champion_name
            and self._model_champion_name != TAKE_TRADE_MODEL_NAME
        ):
            self._logger.warning(
                "take_trade model disabled: MODEL_CHAMPION_NAME=%s != %s",
                self._model_champion_name,
                TAKE_TRADE_MODEL_NAME,
            )
            return None

        sql_v2 = """
            SELECT r.run_id, r.model_name, r.version, r.dataset_hash, r.metrics_json, r.promoted_bool,
                   r.artifact_path, r.target_name, r.output_field, r.calibration_method, r.metadata_json,
                   r.created_ts,
                   g.role AS registry_role,
                   g.calibration_status AS registry_calibration_status,
                   g.activated_ts AS registry_activated_ts,
                   g.scope_type AS registry_scope_type,
                   g.scope_key AS registry_scope_key
            FROM app.model_runs r
            INNER JOIN app.model_registry_v2 g
                ON g.run_id = r.run_id AND g.model_name = r.model_name
            WHERE r.model_name = %s AND g.role = 'champion'
              AND g.scope_type = %s AND g.scope_key = %s
            LIMIT 1
            """

        row = None
        if self._model_registry_v2_enabled:
            scope_attempts: list[tuple[str, str]] = []
            if self._model_registry_scoped_slots_enabled:
                rs = (router_slot or "").strip()
                if rs:
                    scope_attempts.append(("router_slot", rs))
                pb = (playbook_id or "").strip()
                if pb:
                    scope_attempts.append(("playbook", pb))
                sym = (symbol or "").strip().upper()
                if sym:
                    scope_attempts.append(("symbol", sym))
                mf = (market_family or "").strip().lower()
                mr = (market_regime or "").strip().lower()
                if mf and mr:
                    scope_attempts.append(("market_cluster", f"{mf}::{mr}"))
                if mr:
                    scope_attempts.append(("market_regime", mr))
                if mf:
                    scope_attempts.append(("market_family", mf))
            scope_attempts.append(("global", ""))
            with self._connect(row_factory=dict_row) as conn:
                for st, sk in scope_attempts:
                    row = conn.execute(sql_v2, (model_name, st, sk)).fetchone()
                    if row is not None:
                        break
        else:
            sql = """
            SELECT run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
                   artifact_path, target_name, output_field, calibration_method, metadata_json,
                   created_ts,
                   NULL::text AS registry_role,
                   NULL::text AS registry_calibration_status,
                   NULL::timestamptz AS registry_activated_ts,
                   NULL::text AS registry_scope_type,
                   NULL::text AS registry_scope_key
            FROM app.model_runs
            WHERE model_name = %s AND promoted_bool = true
            ORDER BY created_ts DESC
            LIMIT 1
            """
            with self._connect(row_factory=dict_row) as conn:
                row = conn.execute(sql, (model_name,)).fetchone()

        if row is None:
            return None
        out = dict(row)
        if self._model_calibration_required and not production_probability_calibration_satisfied(
            model_name=model_name,
            calibration_method=out.get("calibration_method"),
            metadata_json=out.get("metadata_json"),
        ):
            self._logger.warning(
                "production model blocked (calibration): model_name=%s run_id=%s",
                model_name,
                out.get("run_id"),
            )
            return None
        return out

    def fetch_online_drift_state(self) -> dict[str, Any] | None:
        sql = """
        SELECT effective_action, computed_at, lookback_minutes, breakdown_json
        FROM learn.online_drift_state
        WHERE scope = 'global'
        LIMIT 1
        """
        try:
            with self._connect(row_factory=dict_row) as conn:
                row = conn.execute(sql).fetchone()
        except Exception as exc:
            self._logger.warning("fetch_online_drift_state failed: %s", exc)
            return None
        if row is None:
            return None
        out = dict(row)
        if out.get("computed_at") is not None and hasattr(out["computed_at"], "isoformat"):
            out["computed_at"] = out["computed_at"].isoformat()
        return out

    def get_signal_by_id(self, signal_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT s.*,
            e.explain_version AS explain_version,
            e.explain_short AS explain_short,
            e.explain_long_md AS explain_long_md,
            e.explain_long_json AS explain_long_json,
            e.risk_warnings_json AS risk_warnings_json,
            e.stop_explain_json AS stop_explain_json,
            e.targets_explain_json AS targets_explain_json
        FROM app.signals_v1 s
        LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
        WHERE s.signal_id = %s
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (signal_id,)).fetchone()
        return _signal_row_public(dict(row)) if row else None

    def get_latest_signal(
        self, *, symbol: str, timeframe: str
    ) -> dict[str, Any] | None:
        sql = """
        SELECT s.*,
            e.explain_version AS explain_version,
            e.explain_short AS explain_short,
            e.explain_long_md AS explain_long_md,
            e.explain_long_json AS explain_long_json,
            e.risk_warnings_json AS risk_warnings_json,
            e.stop_explain_json AS stop_explain_json,
            e.targets_explain_json AS targets_explain_json
        FROM app.signals_v1 s
        LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
        WHERE s.symbol = %s AND s.timeframe = %s
        ORDER BY s.analysis_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, timeframe)).fetchone()
        return _signal_row_public(dict(row)) if row else None

    def get_recent_signals(
        self, *, symbol: str, timeframe: str, limit: int
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT s.*,
            e.explain_version AS explain_version,
            e.explain_short AS explain_short,
            e.explain_long_md AS explain_long_md,
            e.explain_long_json AS explain_long_json,
            e.risk_warnings_json AS risk_warnings_json,
            e.stop_explain_json AS stop_explain_json,
            e.targets_explain_json AS targets_explain_json
        FROM app.signals_v1 s
        LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
        WHERE s.symbol = %s AND s.timeframe = %s
        ORDER BY s.analysis_ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, limit)).fetchall()
        return [_signal_row_public(dict(r)) for r in rows]

    def _connect(self, **kwargs: Any) -> psycopg.Connection[Any]:
        kw: dict[str, Any] = {"connect_timeout": 5, "autocommit": True}
        kw.update(kwargs)
        return psycopg.connect(self._database_url, **kw)


def _drawing_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    reasons = row["reasons_json"]
    if isinstance(reasons, str):
        reasons = json.loads(reasons)
    return {
        "drawing_id": str(row["drawing_id"]),
        "parent_id": str(row["parent_id"]),
        "type": row["type"],
        "geometry": row["geometry_json"],
        "reasons": reasons,
        "confidence": float(row["confidence"]),
    }


def _signal_row_public(row: dict[str, Any]) -> dict[str, Any]:
    """Konvertiert DB-Zeile in API-taugliches dict (keine Secrets)."""
    out = dict(row)
    for k in list(out.keys()):
        if isinstance(out[k], Decimal):
            out[k] = float(out[k])
    for jk in (
        "rejection_reasons_json",
        "reasons_json",
        "supporting_drawing_ids_json",
        "supporting_structure_event_ids_json",
        "target_zone_ids_json",
        "source_snapshot_json",
        "signal_components_history_json",
        "regime_reasons_json",
        "target_projection_models_json",
        "uncertainty_reasons_json",
        "ood_reasons_json",
        "abstention_reasons_json",
        "explain_long_json",
        "risk_warnings_json",
        "stop_explain_json",
        "targets_explain_json",
    ):
        if jk in out and isinstance(out[jk], str):
            out[jk] = json.loads(out[jk])
    if "risk_warnings_json" in out:
        rw = out.pop("risk_warnings_json")
        if rw is not None:
            out["risk_warnings"] = rw
    if out.get("explain_long_md") is not None:
        out["explain_long"] = out["explain_long_md"]
    if out.get("stop_zone_id") is not None:
        out["stop_zone_id"] = str(out["stop_zone_id"])
    if out.get("take_trade_model_run_id") is not None:
        out["take_trade_model_run_id"] = str(out["take_trade_model_run_id"])
    if "signal_id" in out:
        out["signal_id"] = str(out["signal_id"])
    if "created_at" in out and out["created_at"] is not None:
        out["created_at"] = out["created_at"].isoformat()
    if "updated_at" in out and out["updated_at"] is not None:
        out["updated_at"] = out["updated_at"].isoformat()
    return out


def all_timeframes() -> tuple[str, ...]:
    return TIMEFRAMES_ORDER


def _timeframe_aliases(timeframe: str) -> list[str]:
    tf = str(timeframe).strip()
    aliases = {tf}
    if tf == "1H":
        aliases.add("1h")
    elif tf == "4H":
        aliases.add("4h")
    return sorted(aliases)
