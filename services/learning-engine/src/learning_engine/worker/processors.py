from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from learning_engine.config import LearningEngineSettings
from learning_engine.e2e.qc import derive_trade_close_qc_labels
from learning_engine.labeling.labels import (
    candle_close_reference,
    compute_exit_stats,
    compute_trade_targets,
    extract_signal_reference_price,
    feature_snapshot_compact,
    parse_stop_plan,
    signal_snapshot_compact,
    structure_snapshot_compact,
    timing_from_events,
)
from learning_engine.labeling.rules_v1 import apply_error_labels
from learning_engine.storage.connection import db_connect
from learning_engine.storage import repo_context, repo_e2e, repo_eval, repo_processed
from shared_py.model_contracts import (
    MODEL_TIMEFRAMES,
    build_model_contract_bundle,
    extract_active_models_from_signal_row,
    normalize_market_regime,
    normalize_feature_row,
    normalize_model_output_row,
    normalize_model_timeframe,
)

logger = logging.getLogger("learning_engine.processor")


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def _resolve_signal_id(
    conn: psycopg.Connection[Any],
    *,
    position_id: UUID,
    symbol: str,
    payload: dict[str, Any],
    meta: dict[str, Any],
) -> UUID | None:
    raw = payload.get("signal_id") or meta.get("strategy_signal_id")
    if raw:
        try:
            return UUID(str(raw))
        except ValueError:
            pass
    st = repo_context.fetch_strategy_state(conn, symbol.upper())
    if st and st.get("last_signal_id"):
        try:
            return UUID(str(st["last_signal_id"]))
        except ValueError:
            return None
    return None


def _collect_learning_quality_issues(
    *,
    settings: LearningEngineSettings,
    decision_ts_ms: int,
    opened_ts_ms: int,
    closed_ts_ms: int,
    side: str,
    entry_avg: Decimal,
    fills: list[dict[str, Any]],
    signal_row: dict[str, Any] | None,
    primary_timeframe: str,
    feature_rows: dict[str, dict[str, Any] | None],
) -> list[str]:
    issues: list[str] = []
    if decision_ts_ms <= 0:
        issues.append("account_decision_ts_invalid")
    if side not in ("long", "short"):
        issues.append("account_side_invalid")
    if entry_avg <= 0:
        issues.append("account_entry_price_invalid")
    if opened_ts_ms > 0 and decision_ts_ms > opened_ts_ms:
        issues.append("decision_after_open")
    if opened_ts_ms <= 0:
        issues.append("account_opened_ts_invalid")
    if closed_ts_ms and closed_ts_ms < opened_ts_ms:
        issues.append("account_closed_before_open")
    if not fills:
        issues.append("missing_trade_fills")
    for fill in fills:
        try:
            price = Decimal(str(fill["price"]))
            qty = Decimal(str(fill["qty_base"]))
        except Exception:
            issues.append("trade_fill_invalid")
            continue
        if price <= 0 or qty <= 0:
            issues.append("trade_fill_invalid")

    primary_tf = normalize_model_timeframe(primary_timeframe)
    primary_feature = feature_rows.get(primary_tf)
    if primary_feature is None:
        issues.append("missing_primary_feature_snapshot")
    for tf, row in feature_rows.items():
        normalized, feature_issues = normalize_feature_row(row)
        if normalized is None:
            issues.append(f"missing_feature_tf_{tf}")
            continue
        if feature_issues:
            issues.append("feature_snapshot_contract_invalid" if tf == primary_tf else f"feature_snapshot_invalid_{tf}")
        computed_ts_ms = int(normalized.get("computed_ts_ms") or 0)
        if computed_ts_ms > 0 and decision_ts_ms - computed_ts_ms > settings.learn_max_feature_age_ms:
            issues.append("stale_feature_snapshot" if tf == primary_tf else f"stale_feature_tf_{tf}")
        if tf == primary_tf:
            liquidity_source = str(normalized.get("liquidity_source") or "").strip()
            if liquidity_source in ("", "missing"):
                issues.append("missing_liquidity_feature_snapshot")
            elif liquidity_source != "orderbook_levels":
                issues.append("liquidity_feature_snapshot_fallback")
            orderbook_age_ms = normalized.get("orderbook_age_ms")
            if orderbook_age_ms is not None and orderbook_age_ms > settings.learn_max_feature_age_ms:
                issues.append("stale_liquidity_feature_snapshot")
            if normalized.get("execution_cost_bps") is None:
                issues.append("missing_execution_cost_snapshot")

            funding_source = str(normalized.get("funding_source") or "").strip()
            if funding_source in ("", "missing"):
                issues.append("missing_funding_feature_snapshot")
            funding_age_ms = normalized.get("funding_age_ms")
            if funding_age_ms is not None and funding_age_ms > settings.learn_max_feature_age_ms:
                issues.append("stale_funding_feature_snapshot")

            open_interest_source = str(normalized.get("open_interest_source") or "").strip()
            if open_interest_source in ("", "missing"):
                issues.append("missing_open_interest_feature_snapshot")
            open_interest_age_ms = normalized.get("open_interest_age_ms")
            if open_interest_age_ms is not None and open_interest_age_ms > settings.learn_max_feature_age_ms:
                issues.append("stale_open_interest_feature_snapshot")
            if normalized.get("open_interest_change_pct") is None:
                issues.append("missing_open_interest_delta_snapshot")

    normalized_signal, signal_issues = normalize_model_output_row(signal_row)
    if normalized_signal is None:
        issues.append("missing_signal_snapshot")
    else:
        if signal_issues:
            issues.append("signal_output_contract_invalid")
        analysis_ts_ms = int(normalized_signal.get("analysis_ts_ms") or 0)
        if analysis_ts_ms > 0 and opened_ts_ms - analysis_ts_ms > settings.learn_stale_signal_ms:
            issues.append("stale_signal_snapshot")

    return sorted(set(issues))


def process_trade_closed(
    settings: LearningEngineSettings,
    envelope: Any,
    *,
    stream: str,
    redis_message_id: str,
) -> None:
    payload = envelope.payload
    pid_raw = payload.get("position_id")
    if not pid_raw:
        logger.warning("trade_closed missing position_id")
        return
    try:
        position_id = UUID(str(pid_raw))
    except ValueError:
        logger.warning("trade_closed invalid position_id=%s", pid_raw)
        return

    with db_connect(settings.database_url) as conn:
        pos = repo_context.fetch_position(conn, position_id)
        if pos is None:
            logger.warning("position not found paper_trade_id=%s", position_id)
            return
        st = str(pos["state"])
        if st not in ("closed", "liquidated"):
            logger.info("skip evaluation position not closed state=%s id=%s", st, position_id)
            return

        fills = repo_context.fetch_fills_ordered(conn, position_id)
        fees = repo_context.sum_fees(conn, position_id)
        funding = repo_context.sum_funding(conn, position_id)
        events = repo_context.fetch_position_events(conn, position_id)
        meta = repo_context.meta_dict(pos.get("meta"))

        symbol = str(pos["symbol"]).upper()
        side = str(pos["side"]).lower()
        entry_avg = _dec(pos["entry_price_avg"])
        opened_ts = int(pos["opened_ts_ms"])
        closed_ts = int(pos["closed_ts_ms"] or 0)
        if closed_ts <= 0 and fills:
            closed_ts = int(fills[-1]["ts_ms"])

        exit_qty, exit_vwap, pnl_gross = compute_exit_stats(fills, side=side, entry_avg=entry_avg)
        if exit_qty <= 0 and fills:
            exit_qty = _dec(fills[0]["qty_base"])
            exit_vwap = _dec(fills[-1]["price"])

        pnl_net = pnl_gross - fees + funding
        direction_correct = pnl_net > 0

        stop_hit, tp1, tp2, tp3, t_tp1, t_stop = timing_from_events(
            events, opened_ts_ms=opened_ts
        )

        sig_id = _resolve_signal_id(
            conn, position_id=position_id, symbol=symbol, payload=payload, meta=meta
        )
        sig_row = repo_context.fetch_signal_v1(conn, sig_id) if sig_id else None
        decision_ts = int((sig_row or {}).get("analysis_ts_ms") or opened_ts)
        tf = normalize_model_timeframe(
            str(
                (sig_row or {}).get("timeframe")
                or meta.get("plan_timeframe")
                or "5m"
            )
        )

        feature_rows: dict[str, dict[str, Any] | None] = {}
        for feature_tf in MODEL_TIMEFRAMES:
            feature_rows[feature_tf] = repo_context.fetch_features_near(
                conn,
                symbol=symbol,
                timeframe=feature_tf,
                ts_ms=decision_ts,
            )
        feat = feature_rows.get(tf)
        feat_4h = feature_rows.get("4H")

        struct_state = repo_context.fetch_structure_state(
            conn, symbol, tf, max_ts_ms=decision_ts
        )
        struct_ev_before = repo_context.fetch_structure_events_before(
            conn, symbol=symbol, timeframe=tf, ts_ms=decision_ts, limit=15
        )
        fb_until = opened_ts + settings.learn_false_breakout_window_ms
        fb_ev = repo_context.fetch_structure_events_around(
            conn, symbol=symbol, timeframe=tf, open_ts_ms=opened_ts, until_ts_ms=fb_until
        )
        false_breakout = [e for e in fb_ev if str(e.get("type")) == "FALSE_BREAKOUT"]

        news_start = decision_ts - settings.news_context_lookback_ms
        news_end = decision_ts
        news_rows = repo_context.fetch_news_window(conn, start_ms=news_start, end_ms=news_end)
        news_json = json.loads(json.dumps([dict(r) for r in news_rows], default=str))

        stop_plan = parse_stop_plan(pos)
        stop_qs = pos.get("stop_quality_score")
        stop_price_for_labels: Decimal | None = None
        if stop_plan:
            try:
                stop_price_for_labels = _dec(stop_plan["stop_price"])
            except (KeyError, ArithmeticError, ValueError, TypeError):
                stop_price_for_labels = None
        stop_dist_atr: Decimal | None = None
        if stop_price_for_labels is not None and feat:
            try:
                atr_v = feat.get("atr_14")
                if atr_v is not None and float(atr_v) > 0:
                    atr_d = Decimal(str(atr_v))
                    stop_dist_atr = abs(entry_avg - stop_price_for_labels) / atr_d
            except (ArithmeticError, ValueError, TypeError):
                pass

        multi_tf = None
        if sig_row and sig_row.get("multi_timeframe_score_0_100") is not None:
            multi_tf = float(sig_row["multi_timeframe_score_0_100"])

        f4trend = None
        if feat_4h and feat_4h.get("trend_dir") is not None:
            f4trend = int(feat_4h["trend_dir"])

        stale = False
        if sig_row and sig_row.get("analysis_ts_ms") is not None:
            stale = opened_ts - int(sig_row["analysis_ts_ms"]) > settings.learn_stale_signal_ms

        news_shock = False
        try:
            news_shock = repo_context.has_news_shock_strategy_event(conn, position_id)
        except Exception:
            news_shock = False

        quality_issues = _collect_learning_quality_issues(
            settings=settings,
            decision_ts_ms=decision_ts,
            opened_ts_ms=opened_ts,
            closed_ts_ms=closed_ts,
            side=side,
            entry_avg=entry_avg,
            fills=fills,
            signal_row=sig_row,
            primary_timeframe=tf,
            feature_rows=feature_rows,
        )

        err_labels = apply_error_labels(
            settings=settings,
            stop_distance_atr_mult=stop_dist_atr,
            false_breakout_events=false_breakout,
            multi_tf_score=multi_tf,
            feature_4h_trend=f4trend,
            side=side,
            news_shock=news_shock,
            stale_signal=stale,
        )
        if quality_issues:
            err_labels = sorted(set(err_labels + ["DATA_QUALITY_GATE_FAILED"]))

        regime = normalize_market_regime((sig_row or {}).get("market_regime"))
        if regime is None:
            regime = normalize_market_regime(struct_state.get("trend_dir") if struct_state else None)

        qty_eval = (
            exit_qty
            if exit_qty > 0
            else (_dec(fills[0]["qty_base"]) if fills else Decimal("0"))
        )
        entry_qty = _dec(fills[0]["qty_base"]) if fills else qty_eval

        entry_reference_price = extract_signal_reference_price(sig_row)
        if entry_reference_price is None:
            entry_ref_candle = repo_context.fetch_latest_candle_before(
                conn, symbol=symbol, timeframe="1m", ts_ms=decision_ts
            )
            if entry_ref_candle is None and tf != "1m":
                entry_ref_candle = repo_context.fetch_latest_candle_before(
                    conn, symbol=symbol, timeframe=tf, ts_ms=decision_ts
                )
            entry_reference_price = candle_close_reference(entry_ref_candle)

        label_path: list[dict[str, Any]] = []
        if closed_ts > decision_ts:
            label_path = repo_context.fetch_candles_window(
                conn,
                symbol=symbol,
                timeframe="1m",
                start_ts_ms=decision_ts,
                end_ts_ms=closed_ts,
            )
            if not label_path and tf != "1m":
                label_path = repo_context.fetch_candles_window(
                    conn,
                    symbol=symbol,
                    timeframe=tf,
                    start_ts_ms=decision_ts,
                    end_ts_ms=closed_ts,
                )

        exit_reference_price = candle_close_reference(label_path[-1]) if label_path else None
        if exit_reference_price is None and closed_ts > 0:
            exit_ref_candle = repo_context.fetch_latest_candle_before(
                conn, symbol=symbol, timeframe="1m", ts_ms=closed_ts
            )
            if exit_ref_candle is None and tf != "1m":
                exit_ref_candle = repo_context.fetch_latest_candle_before(
                    conn, symbol=symbol, timeframe=tf, ts_ms=closed_ts
                )
            exit_reference_price = candle_close_reference(exit_ref_candle)

        isolated_margin = (
            _dec(pos["isolated_margin"]) if pos.get("isolated_margin") is not None else None
        )
        target_comp = compute_trade_targets(
            side=side,
            state=st,
            decision_ts_ms=decision_ts,
            opened_ts_ms=opened_ts,
            evaluation_end_ts_ms=closed_ts,
            qty_base=entry_qty,
            entry_price_avg=entry_avg,
            exit_price_avg=exit_vwap if exit_vwap > 0 else None,
            pnl_net_usdt=pnl_net,
            entry_reference_price=entry_reference_price,
            exit_reference_price=exit_reference_price,
            path_candles=label_path,
            isolated_margin=isolated_margin,
            fees_total_usdt=fees,
            funding_total_usdt=funding,
            maintenance_margin_rate=_dec(settings.paper_mmr_base),
            liq_fee_buffer_usdt=_dec(settings.paper_liq_fee_buffer_usdt),
            market_regime=regime,
            stop_price=stop_price_for_labels,
        )
        target_labels = target_comp.labels

        eval_row: dict[str, Any] = {
            "paper_trade_id": position_id,
            "signal_id": sig_id,
            "symbol": symbol,
            "timeframe": tf,
            "decision_ts_ms": target_labels.decision_ts_ms,
            "opened_ts_ms": opened_ts,
            "closed_ts_ms": closed_ts,
            "side": side,
            "qty_base": qty_eval,
            "entry_price_avg": entry_avg,
            "exit_price_avg": exit_vwap if exit_vwap > 0 else None,
            "pnl_gross_usdt": pnl_gross,
            "fees_total_usdt": fees,
            "funding_total_usdt": funding,
            "pnl_net_usdt": pnl_net,
            "direction_correct": direction_correct,
            "stop_hit": stop_hit,
            "tp1_hit": tp1,
            "tp2_hit": tp2,
            "tp3_hit": tp3,
            "time_to_tp1_ms": t_tp1,
            "time_to_stop_ms": t_stop,
            "stop_quality_score": int(stop_qs) if stop_qs is not None else None,
            "stop_distance_atr_mult": stop_dist_atr,
            "slippage_bps_entry": target_labels.slippage_bps_entry,
            "slippage_bps_exit": target_labels.slippage_bps_exit,
            "market_regime": regime,
            "take_trade_label": target_labels.take_trade_label,
            "expected_return_bps": target_labels.expected_return_bps,
            "expected_return_gross_bps": target_labels.expected_return_gross_bps,
            "expected_mae_bps": target_labels.expected_mae_bps,
            "expected_mfe_bps": target_labels.expected_mfe_bps,
            "liquidation_proximity_bps": target_labels.liquidation_proximity_bps,
            "liquidation_risk": target_labels.liquidation_risk,
            "news_context_json": news_json,
            "signal_snapshot_json": signal_snapshot_compact(sig_row),
            "feature_snapshot_json": feature_snapshot_compact(
                primary_timeframe=tf,
                primary_feature=feat,
                features_by_tf=feature_rows,
                quality_issues=quality_issues,
            ),
            "structure_snapshot_json": structure_snapshot_compact(struct_state, struct_ev_before),
            "error_labels_json": err_labels,
            "model_contract_json": build_model_contract_bundle(
                quality_issues=quality_issues,
                active_models=extract_active_models_from_signal_row(sig_row),
                target_labeling_audit=target_comp.audit,
            ),
        }

        with conn.transaction():
            eval_uuid = repo_eval.upsert_trade_evaluation(conn, eval_row)
            if sig_id:
                repo_eval.upsert_signal_outcome(
                    conn, signal_id=sig_id, direction_correct=direction_correct
                )
            if sig_id:
                ttp = None
                if sig_row and sig_row.get("take_trade_prob") is not None:
                    try:
                        ttp = float(sig_row["take_trade_prob"])
                    except (TypeError, ValueError):
                        ttp = None
                qc_patch = derive_trade_close_qc_labels(
                    err_labels=err_labels,
                    direction_correct=bool(eval_row["direction_correct"]),
                    stop_hit=bool(eval_row["stop_hit"]),
                    tp1_hit=bool(eval_row["tp1_hit"]),
                    take_trade_prob=ttp,
                    pnl_net=pnl_net,
                )
                outcome_paper = {
                    "pnl_net_usdt": str(pnl_net),
                    "direction_correct": bool(eval_row["direction_correct"]),
                    "stop_hit": bool(eval_row["stop_hit"]),
                    "tp1_hit": bool(eval_row["tp1_hit"]),
                    "tp2_hit": bool(eval_row["tp2_hit"]),
                    "tp3_hit": bool(eval_row["tp3_hit"]),
                    "closed_ts_ms": closed_ts,
                }
                repo_e2e.ensure_record_from_signal_if_missing(conn, sig_row)
                repo_e2e.merge_paper_trade_closed(
                    conn,
                    signal_id=sig_id,
                    paper_trade_id=position_id,
                    evaluation_id=eval_uuid,
                    outcome_paper=outcome_paper,
                    label_qc_patch=qc_patch,
                    operator_meta=meta,
                )
            repo_processed.mark_processed(conn, stream, redis_message_id)

        if settings.learn_ai_attribution_enabled and sig_id is not None:
            try:
                from learning_engine.worker import ai_attribution

                ai_attribution.run_ai_attribution_for_evaluation(
                    conn,
                    settings,
                    evaluation_id=eval_uuid,
                    eval_row=eval_row,
                    sig_row=sig_row,
                    decision_ts_ms=int(target_labels.decision_ts_ms),
                    primary_timeframe=tf,
                )
            except Exception as exc:
                logger.warning("ai_attribution: %s", exc, exc_info=False)

        logger.info(
            "processed trade_closed paper_trade_id=%s pnl_net_usdt=%s",
            position_id,
            eval_row["pnl_net_usdt"],
        )


def process_signal_created(
    settings: LearningEngineSettings,
    envelope: Any,
    *,
    stream: str,
    redis_message_id: str,
) -> None:
    payload = envelope.payload or {}
    raw = payload.get("signal_id")
    if not raw:
        logger.warning("signal_created missing signal_id")
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                repo_processed.mark_processed(conn, stream, redis_message_id)
        return
    try:
        sig_id = UUID(str(raw))
    except ValueError:
        logger.warning("signal_created invalid signal_id=%s", raw)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                repo_processed.mark_processed(conn, stream, redis_message_id)
        return

    with db_connect(settings.database_url) as conn:
        row = None
        for _ in range(4):
            row = repo_context.fetch_signal_v1(conn, sig_id)
            if row is not None:
                break
            time.sleep(0.05)
        with conn.transaction():
            if row is not None:
                repo_e2e.upsert_decision_record_from_signal(conn, row)
            else:
                logger.warning("e2e: signal row missing after retry signal_id=%s", sig_id)
            repo_processed.mark_processed(conn, stream, redis_message_id)
    logger.info("e2e decision record upsert signal_id=%s ok=%s", sig_id, row is not None)


def process_trade_opened(
    settings: LearningEngineSettings,
    envelope: Any,
    *,
    stream: str,
    redis_message_id: str,
) -> None:
    payload = envelope.payload or {}
    pid_raw = payload.get("position_id")
    if not pid_raw:
        logger.warning("trade_opened missing position_id")
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                repo_processed.mark_processed(conn, stream, redis_message_id)
        return
    try:
        position_id = UUID(str(pid_raw))
    except ValueError:
        logger.warning("trade_opened invalid position_id=%s", pid_raw)
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                repo_processed.mark_processed(conn, stream, redis_message_id)
        return

    sig_id: UUID | None = None
    with db_connect(settings.database_url) as conn:
        pos = repo_context.fetch_position(conn, position_id)
        if pos is None:
            logger.warning("trade_opened position not found %s", position_id)
            with conn.transaction():
                repo_processed.mark_processed(conn, stream, redis_message_id)
            return
        meta = repo_context.meta_dict(pos.get("meta"))
        symbol = str(pos["symbol"]).upper()
        sig_id = _resolve_signal_id(
            conn,
            position_id=position_id,
            symbol=symbol,
            payload=payload,
            meta=meta,
        )
        with conn.transaction():
            if sig_id:
                sig_row = repo_context.fetch_signal_v1(conn, sig_id)
                repo_e2e.ensure_record_from_signal_if_missing(conn, sig_row)
                repo_e2e.merge_paper_trade_opened(
                    conn,
                    signal_id=sig_id,
                    paper_trade_id=position_id,
                    opened_ts_ms=int(pos.get("opened_ts_ms") or 0),
                    side=str(pos.get("side") or "").lower(),
                )
            repo_processed.mark_processed(conn, stream, redis_message_id)
    logger.info("e2e paper open linked position_id=%s signal_id=%s", position_id, sig_id)
