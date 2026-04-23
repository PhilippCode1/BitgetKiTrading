from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from shared_py.modul_mate_db_gates import assert_execution_allowed
from shared_py.product_policy import ExecutionPolicyViolationError

from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetInstrumentMetadataService,
    UnknownInstrumentError,
)
from shared_py.eventbus import EventEnvelope, RedisStreamBus
from shared_py.operator_intel import build_operator_intel_envelope_payload
from shared_py.exit_family_resolver import extract_exit_execution_hints_from_trace
from shared_py.exit_engine import build_live_exit_plans, merge_exit_build_overrides, validate_exit_plan
from shared_py.observability.correlation import log_correlation_fields
from shared_py.observability.execution_forensic import (
    build_live_broker_forensic_snapshot,
    redact_operator_journal_details,
)
from shared_py.shadow_live_divergence import assess_shadow_live_divergence

from live_broker.config import LiveBrokerSettings
from live_broker.exchange_client import BitgetExchangeClient
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.risk_adapter import build_live_trade_risk_decision
from live_broker.events import publish_operator_intel
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import BitgetRestError

logger = logging.getLogger("live_broker.execution")
SECURITY = logging.getLogger("live_broker.security")


def _intent_under_survival_mode(intent: ExecutionIntentRequest) -> ExecutionIntentRequest:
    from shared_py.resilience.survival_kernel import apply_survival_signal_overrides

    nested = intent.payload.get("signal_payload")
    base = dict(nested) if isinstance(nested, dict) else dict(intent.payload)
    merged = apply_survival_signal_overrides(base)
    if isinstance(nested, dict):
        new_payload = {
            **intent.payload,
            "signal_payload": merged,
            "signal_allowed_leverage": 1,
            "signal_recommended_leverage": 1,
        }
    else:
        new_payload = {**intent.payload, **merged}
        new_payload["signal_allowed_leverage"] = 1
        new_payload["signal_recommended_leverage"] = 1
    return intent.model_copy(update={"leverage": 1, "payload": new_payload})


def _coerce_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_text_from_payload(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _signal_router_arbitration(signal_payload: dict[str, Any]) -> dict[str, Any]:
    specialists = signal_payload.get("specialists")
    if isinstance(specialists, dict):
        router = specialists.get("router_arbitration")
        if isinstance(router, dict):
            return router
    reasons_json = signal_payload.get("reasons_json")
    reasons_json = reasons_json if isinstance(reasons_json, dict) else {}
    specialists = reasons_json.get("specialists")
    specialists = specialists if isinstance(specialists, dict) else {}
    router = specialists.get("router_arbitration")
    return router if isinstance(router, dict) else {}


def _signal_decision_control_flow(signal_payload: dict[str, Any]) -> dict[str, Any]:
    dcf = signal_payload.get("decision_control_flow")
    if isinstance(dcf, dict):
        return dcf
    reasons_json = signal_payload.get("reasons_json")
    reasons_json = reasons_json if isinstance(reasons_json, dict) else {}
    dcf = reasons_json.get("decision_control_flow")
    return dcf if isinstance(dcf, dict) else {}


class LiveExecutionService:
    def __init__(
        self,
        settings: LiveBrokerSettings,
        exchange_client: BitgetExchangeClient,
        repo: LiveBrokerRepository,
        catalog: BitgetInstrumentCatalog | None = None,
        metadata_service: BitgetInstrumentMetadataService | None = None,
    ) -> None:
        self._settings = settings
        self._exchange_client = exchange_client
        self._repo = repo
        self._catalog = catalog
        self._metadata_service = metadata_service
        self._truth_state_fn: Callable[[], dict[str, Any]] | None = None
        self._event_bus: RedisStreamBus | None = None

    def set_event_bus(self, bus: RedisStreamBus | None) -> None:
        self._event_bus = bus

    def set_truth_state_fn(self, fn: Callable[[], dict[str, Any]] | None) -> None:
        self._truth_state_fn = fn

    def _assert_db_live_execution_policy(self) -> None:
        if not self._settings.commercial_gates_enforced_for_exchange_submit:
            return
        dsn = (self._settings.database_url or "").strip()
        if not dsn:
            raise ExecutionPolicyViolationError(
                "LIVE-Execution: DATABASE_URL fehlt bei aktivem commercial gate",
                reason="database_url_required_for_gates",
            )
        tid = (self._settings.modul_mate_gate_tenant_id or "default").strip()
        try:
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
                assert_execution_allowed(conn, tenant_id=tid, mode="LIVE")
        except ExecutionPolicyViolationError as exc:
            SECURITY.warning(
                "[SECURITY_WARNING] execution blocked tenant_id=%s reason=%s msg=%s",
                tid,
                exc.reason,
                str(exc)[:500],
            )
            raise

    def _maybe_publish_operator_intel_execution(
        self,
        *,
        saved: dict[str, Any],
        intent: ExecutionIntentRequest,
        action: str,
        reason: str,
        requested_mode: str,
        effective_mode: str,
        risk_decision: dict[str, Any],
    ) -> None:
        if not self._settings.live_operator_intel_outbox_enabled or self._event_bus is None:
            return
        ex_id = str(saved.get("execution_id") or "").strip()
        if not ex_id:
            return
        if action == "blocked":
            kind = "no_trade"
            severity = "warn"
        elif action in ("live_candidate_recorded", "shadow_recorded"):
            kind = "strategy_intent"
            severity = "info"
        else:
            kind = "execution_update"
            severity = "info"
        risk_summary = ""
        if isinstance(risk_decision, dict):
            risk_summary = str(
                risk_decision.get("decision_reason")
                or risk_decision.get("primary_reason")
                or risk_decision.get("trade_action")
                or ""
            )[:220]
        metrics = risk_decision.get("metrics") if isinstance(risk_decision, dict) else {}
        lev_allowed = metrics.get("allowed_leverage") if isinstance(metrics, dict) else None
        leverage_band = f"intent_lev={intent.leverage} risk_allowed={lev_allowed}"
        sp = self._signal_payload(intent)
        router = _signal_router_arbitration(sp)
        dcf = _signal_decision_control_flow(sp)
        end_binding = dcf.get("end_decision_binding") if isinstance(dcf.get("end_decision_binding"), dict) else {}
        playbook_id = str(sp.get("playbook_id") or "").strip() or None
        regime_guess = str(sp.get("market_regime") or "").strip() or None
        specialist_route = " / ".join(
            part
            for part in (
                str(router.get("router_id") or "").strip(),
                str(router.get("selected_trade_action") or "").strip(),
            )
            if part
        )
        stop_fragility = sp.get("stop_fragility_0_1")
        stop_exec = sp.get("stop_executability_0_1")
        if stop_fragility is not None or stop_exec is not None:
            leverage_band = f"{leverage_band} stop_fragility={stop_fragility} stop_exec={stop_exec}"
        pl = build_operator_intel_envelope_payload(
            intel_kind=kind,
            symbol=str(intent.symbol),
            correlation_id=f"exec:{ex_id}",
            market_family=str(intent.market_family or self._settings.market_family),
            playbook_id=playbook_id,
            specialist_route=specialist_route or f"execution:{intent.source_service}",
            regime=regime_guess,
            risk_summary=risk_summary or None,
            stop_exit_family=(
                str(end_binding.get("exit_family_effective_primary") or end_binding.get("exit_family_primary") or "").strip()
                or None
            ),
            leverage_band=leverage_band,
            reasons=[reason, f"effective_mode={effective_mode}", f"requested={requested_mode}"][:10],
            outcome=f"action={action}",
            execution_id=ex_id,
            signal_id=str(intent.signal_id) if intent.signal_id else None,
            severity=severity,
            dedupe_key=f"opintel:exec:{ex_id}:{action}",
            dedupe_ttl_minutes=3,
            notes=(
                f"Live-Submit bleibt operator-gated; Telegram aendert keine Policy. "
                f"mirror_eligible={saved.get('payload_json', {}).get('live_mirror_eligible')}"
                if isinstance(saved.get("payload_json"), dict)
                else "Live-Submit bleibt operator-gated; Telegram aendert keine Policy."
            ),
        )
        try:
            publish_operator_intel(
                self._event_bus,
                symbol=str(intent.symbol),
                timeframe=intent.timeframe,
                payload=pl,
                trace={"source": "live-broker-execution"},
            )
        except Exception as exc:
            logger.warning("operator_intel publish failed: %s", exc)

    def _maybe_publish_operator_intel_release(
        self,
        *,
        execution_id: str,
        symbol: str,
        source: str,
    ) -> None:
        if not self._settings.live_operator_intel_outbox_enabled or self._event_bus is None:
            return
        sym = (symbol or "").strip() or "?"
        pl = build_operator_intel_envelope_payload(
            intel_kind="plan_summary",
            symbol=sym,
            correlation_id=f"exec:{execution_id}",
            outcome="operator_release_recorded",
            execution_id=execution_id,
            reasons=[f"source={source}"],
            severity="info",
            dedupe_key=f"opintel:exec:release:{execution_id}",
            dedupe_ttl_minutes=60,
            notes="Operator-Freigabe protokolliert (keine Strategie-Mutation).",
        )
        try:
            publish_operator_intel(
                self._event_bus,
                symbol=sym,
                payload=pl,
                trace={"source": "live-broker-execution"},
            )
        except Exception as exc:
            logger.warning("operator_intel release publish failed: %s", exc)

    def truth_status_snapshot(self) -> dict[str, Any]:
        gate = bool(self._settings.live_broker_block_live_without_exchange_truth)
        if self._truth_state_fn is None:
            return {"configured": False, "gate_enabled": gate}
        st = self._truth_state_fn()
        allow, reason = self._evaluate_exchange_truth(st)
        return {
            "configured": True,
            "gate_enabled": gate,
            "live_submit_allowed_by_truth": allow,
            "truth_block_reason": None if allow else reason,
            **st,
        }

    def _evaluate_exchange_truth(self, st: dict[str, Any]) -> tuple[bool, str]:
        if not self._settings.live_broker_block_live_without_exchange_truth:
            return True, "gate_disabled"
        if st.get("safety_latch_blocks_live"):
            return False, "live_safety_latch_active"
        if st.get("drift_blocked"):
            return False, "exchange_drift_or_snapshot_unhealthy"
        if st.get("truth_channel_ok"):
            return True, str(st.get("truth_reason") or "ok")
        return False, str(st.get("truth_reason") or "no_fresh_exchange_truth_channel")

    def _live_exchange_truth_allows_submit(self) -> tuple[bool, str]:
        if self._truth_state_fn is None:
            return True, "no_truth_fn"
        return self._evaluate_exchange_truth(self._truth_state_fn())

    def _persist_execution_audit_sidecars(
        self,
        *,
        saved: dict[str, Any],
        risk_decision: dict[str, Any],
        shadow_live_report: dict[str, Any] | None,
        final_reason: str,
        intent: ExecutionIntentRequest,
    ) -> None:
        exec_id = saved.get("execution_id")
        if not exec_id:
            return
        eid = str(exec_id)
        try:
            self._repo.record_execution_risk_snapshot(eid, risk_decision)
        except Exception as exc:
            logger.warning(
                "execution risk snapshot skipped execution_id=%s err=%s",
                eid,
                exc,
            )
        if shadow_live_report is None:
            return
        try:
            self._repo.record_shadow_live_assessment(
                execution_decision_id=eid,
                source_signal_id=intent.signal_id,
                symbol=intent.symbol,
                match_ok=bool(shadow_live_report.get("match_ok")),
                gate_blocked=final_reason == "shadow_live_divergence_gate",
                report=shadow_live_report,
            )
        except Exception as exc:
            logger.warning(
                "shadow_live assessment skipped execution_id=%s err=%s",
                eid,
                exc,
            )

    def interfaces_payload(self) -> dict[str, Any]:
        return {
            "execution_mode": self._settings.execution_mode,
            "strategy_execution_mode": self._settings.strategy_execution_mode,
            "market_family": self._settings.market_family,
            "paper_path_active": self._settings.paper_path_active,
            "shadow_trade_enable": self._settings.shadow_trade_enable,
            "live_trade_enable": self._settings.live_trade_enable,
            "signal_engine_stream": self._settings.live_broker_signal_stream,
            "paper_broker_reference_streams": self._settings.reference_streams,
            "api_gateway_routes": (
                "/v1/live-broker/runtime",
                "/v1/live-broker/decisions/recent",
                "/v1/live-broker/reference/paper",
            ),
            "live_broker_order_routes": (
                "/live-broker/orders/create",
                "/live-broker/orders/reduce-only",
                "/live-broker/orders/cancel",
                "/live-broker/orders/replace",
                "/live-broker/orders/query",
                "/live-broker/kill-switch/arm",
                "/live-broker/kill-switch/release",
                "/live-broker/orders/emergency-flatten",
                "/live-broker/safety/orders/cancel-all",
                "/live-broker/safety/safety-latch/release",
                "/live-broker/orders/timeouts/run",
            ),
            "monitor_engine_service_name": "live-broker",
            "shadow_path_active": self._settings.shadow_path_active,
            "live_order_submission_enabled": self._settings.live_order_submission_enabled,
            "require_shadow_match_before_live": self._settings.require_shadow_match_before_live,
            "shadow_live_thresholds": asdict(self._settings.shadow_live_thresholds()),
            "instrument": self._settings.instrument_identity().model_dump(mode="json"),
        }

    def evaluate_intent(
        self,
        intent: ExecutionIntentRequest,
        *,
        probe_exchange: bool = True,
    ) -> dict[str, Any]:
        truth = self._truth_state_fn() or {} if self._truth_state_fn else {}
        survival = bool(truth.get("survival_mode_active"))
        survival_lock = bool(truth.get("survival_execution_lock"))
        intent_eval = _intent_under_survival_mode(intent) if survival else intent

        requested_mode = intent_eval.requested_runtime_mode
        effective_mode = self._effective_runtime_mode(requested_mode)
        if effective_mode == "live":
            self._assert_db_live_execution_policy()

        preview = self._exchange_client.build_order_preview(intent_eval)
        probe = (
            self._exchange_client.probe_exchange()
            if probe_exchange
            else {
                **self._exchange_client.describe(),
                "public_api_ok": None,
                "public_detail": "not_requested",
                "private_api_configured": self._exchange_client.private_api_configured()[0],
                "private_detail": self._exchange_client.private_api_configured()[1],
                "market_snapshot": {},
            }
        )

        catalog_entry = self._resolve_catalog_entry(intent_eval)
        metadata = self._resolve_metadata(intent_eval)
        signal_payload = self._signal_payload(intent_eval)
        router_arb = _signal_router_arbitration(signal_payload)
        exit_preview = self._exit_preview(intent_eval)
        now_ms = int(time.time() * 1000)
        risk_decision = build_live_trade_risk_decision(
            settings=self._settings,
            repo=self._repo,
            intent=intent_eval,
            signal_payload=signal_payload,
            now_ms=now_ms,
            survival_mode_active=survival,
        )
        action, reason = self._decide(
            intent_eval,
            requested_mode,
            effective_mode,
            probe,
            exit_preview=exit_preview,
            risk_decision=risk_decision,
            shadow_path_simulation=False,
            survival_execution_lock=survival_lock,
        )

        shadow_live_report: dict[str, Any] | None = None
        if effective_mode == "live":
            shadow_action, shadow_reason = self._decide(
                intent_eval,
                requested_mode,
                "shadow",
                probe,
                exit_preview=exit_preview,
                risk_decision=risk_decision,
                shadow_path_simulation=True,
                survival_execution_lock=survival_lock,
            )
            shadow_live_report = assess_shadow_live_divergence(
                shadow_decision=(shadow_action, shadow_reason),
                live_decision=(action, reason),
                signal_payload=signal_payload,
                risk_decision=risk_decision,
                intent_leverage=intent_eval.leverage,
                now_ms=now_ms,
                exit_preview=exit_preview,
                thresholds=self._settings.shadow_live_thresholds(),
            )
            if (
                self._settings.require_shadow_match_before_live
                and not shadow_live_report["match_ok"]
                and action == "live_candidate_recorded"
            ):
                action, reason = "blocked", "shadow_live_divergence_gate"
        live_mirror_eligible = bool(
            effective_mode == "live"
            and action == "live_candidate_recorded"
            and str(signal_payload.get("trade_action") or "").strip().lower() == "allow_trade"
            and (
                shadow_live_report is None
                or bool(shadow_live_report.get("match_ok"))
            )
        )

        record = {
            "source_service": intent_eval.source_service,
            "source_signal_id": intent_eval.signal_id,
            "symbol": intent_eval.symbol,
            "timeframe": intent_eval.timeframe,
            "direction": intent_eval.direction,
            "requested_runtime_mode": requested_mode,
            "effective_runtime_mode": effective_mode,
            "decision_action": action,
            "decision_reason": reason,
            "order_type": intent_eval.order_type,
            "leverage": intent_eval.leverage,
            "approved_7x": intent_eval.approved_7x,
            "qty_base": intent_eval.qty_base,
            "entry_price": intent_eval.entry_price,
            "stop_loss": intent_eval.stop_loss,
            "take_profit": intent_eval.take_profit,
            "payload_json": {
                **intent_eval.payload,
                "note": intent_eval.note,
                "catalog_instrument": (
                    catalog_entry.model_dump(mode="json") if catalog_entry is not None else None
                ),
                "instrument_metadata": metadata.model_dump(mode="json") if metadata is not None else None,
                "exchange_preview": preview,
                "exchange_probe": {
                    "public_api_ok": probe.get("public_api_ok"),
                    "public_detail": probe.get("public_detail"),
                    "private_api_configured": probe.get("private_api_configured"),
                    "private_detail": probe.get("private_detail"),
                    "market_snapshot": probe.get("market_snapshot"),
                },
                "exit_preview": exit_preview,
                "risk_engine": risk_decision,
                "live_mirror_eligible": live_mirror_eligible,
                **(
                    {"shadow_live_divergence": shadow_live_report}
                    if shadow_live_report is not None
                    else {}
                ),
            },
            "trace_json": {
                **intent_eval.trace,
                "source_service": intent_eval.source_service,
                "requested_runtime_mode": requested_mode,
                "effective_runtime_mode": effective_mode,
                **(
                    {"catalog_instrument": catalog_entry.model_dump(mode="json")}
                    if catalog_entry is not None
                    else {}
                ),
                **(
                    {"instrument_metadata": metadata.model_dump(mode="json")}
                    if metadata is not None
                    else {}
                ),
                "exit_preview": exit_preview,
                "risk_engine": risk_decision,
                "live_mirror_eligible": live_mirror_eligible,
                **(
                    {"shadow_live_divergence": shadow_live_report}
                    if shadow_live_report is not None
                    else {}
                ),
            },
        }
        saved = self._repo.record_execution_decision(record)
        ex_id = saved.get("execution_id")
        if ex_id is not None:
            try:
                pay = signal_payload if isinstance(signal_payload, dict) else {}
                tr = intent_eval.trace if isinstance(intent_eval.trace, dict) else {}
                forensic = build_live_broker_forensic_snapshot(
                    signal_payload=pay,
                    risk_decision=risk_decision if isinstance(risk_decision, dict) else None,
                    shadow_live_report=shadow_live_report
                    if isinstance(shadow_live_report, dict)
                    else None,
                    trace=tr,
                )
                self._repo.record_execution_journal(
                    {
                        "execution_decision_id": str(ex_id),
                        "internal_order_id": None,
                        "phase": "execution_decision",
                        "details_json": {
                            "decision_action": action,
                            "decision_reason": reason,
                            "symbol": intent_eval.symbol,
                            "requested_runtime_mode": requested_mode,
                            "effective_runtime_mode": effective_mode,
                            "forensic_snapshot": forensic,
                        },
                    }
                )
            except Exception as exc:
                logger.warning(
                    "execution journal execution_decision failed execution_id=%s err=%s",
                    ex_id,
                    exc,
                )
        self._persist_execution_audit_sidecars(
            saved=saved,
            risk_decision=risk_decision,
            shadow_live_report=shadow_live_report,
            final_reason=reason,
            intent=intent_eval,
        )
        ev_id = None
        if isinstance(intent_eval.payload, dict):
            ev_id = intent_eval.payload.get("event_id")
            if ev_id is not None:
                ev_id = str(ev_id)
        logger.info(
            (
                "live-broker decision action=%s reason=%s source=%s symbol=%s "
                "requested=%s effective=%s mirror_eligible=%s router_id=%s stop_fragility=%s"
            ),
            action,
            reason,
            intent_eval.source_service,
            intent_eval.symbol,
            requested_mode,
            effective_mode,
            live_mirror_eligible,
            router_arb.get("router_id"),
            signal_payload.get("stop_fragility_0_1"),
            extra=log_correlation_fields(
                signal_id=str(intent_eval.signal_id) if intent_eval.signal_id else None,
                execution_id=str(ex_id) if ex_id else None,
                event_id=ev_id,
                symbol=str(intent_eval.symbol) if intent_eval.symbol else None,
            ),
        )
        self._maybe_publish_operator_intel_execution(
            saved=saved,
            intent=intent_eval,
            action=str(action),
            reason=str(reason),
            requested_mode=str(requested_mode),
            effective_mode=str(effective_mode),
            risk_decision=risk_decision,
        )
        return saved

    def telegram_operator_release_summary(self, execution_id: str) -> dict[str, Any]:
        """
        Lesender Snapshot fuer Telegram-Zweistufen-Freigabe (keine Secrets, keine payload_json).
        Nur bestehende KI-Execution-IDs; Freigabe nur fuer live-Kandidaten ohne bestehendes Release.
        """
        row = self._repo.get_execution_decision(execution_id)
        if row is None:
            return {
                "found": False,
                "eligible": False,
                "reason": "not_found",
                "execution_id": execution_id,
            }
        rel = self._repo.get_operator_release(execution_id)
        action = str(row.get("decision_action") or "")
        eff = str(row.get("effective_runtime_mode") or "")
        if rel is not None:
            return {
                "found": True,
                "eligible": False,
                "reason": "already_released",
                "execution_id": execution_id,
                "summary": self._telegram_safe_execution_summary(row),
            }
        eligible = action == "live_candidate_recorded" and eff == "live"
        reason = "ok" if eligible else "not_eligible_for_telegram_release"
        return {
            "found": True,
            "eligible": bool(eligible),
            "reason": reason,
            "execution_id": execution_id,
            "summary": self._telegram_safe_execution_summary(row),
        }

    @staticmethod
    def _telegram_safe_execution_summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": row.get("symbol"),
            "timeframe": row.get("timeframe"),
            "direction": row.get("direction"),
            "decision_action": row.get("decision_action"),
            "decision_reason": row.get("decision_reason"),
            "effective_runtime_mode": row.get("effective_runtime_mode"),
            "requested_runtime_mode": row.get("requested_runtime_mode"),
            "source_service": row.get("source_service"),
            "source_signal_id": row.get("source_signal_id"),
            "leverage": row.get("leverage"),
            "order_type": row.get("order_type"),
            "created_ts": row.get("created_ts"),
        }

    def record_operator_release(
        self,
        execution_id: str,
        *,
        source: str = "internal-api",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        allowed_sources = frozenset({"internal-api", "telegram_operator", "manual", "reconcile"})
        src = str(source or "internal-api").strip() or "internal-api"
        if src not in allowed_sources:
            raise BitgetRestError(
                classification="validation",
                message=f"operator_release source nicht erlaubt: {src}",
                retryable=False,
            )
        existing = self._repo.get_execution_decision(execution_id)
        if existing is None:
            raise BitgetRestError(
                classification="not_found",
                message=f"execution_id nicht gefunden: {execution_id}",
                retryable=False,
            )
        rel = self._repo.record_operator_release(
            execution_id=execution_id,
            source=src,
            details=details,
        )
        try:
            safe_details = redact_operator_journal_details(details)
            self._repo.record_execution_journal(
                {
                    "execution_decision_id": execution_id,
                    "internal_order_id": None,
                    "phase": "operator_release",
                    "details_json": {"source": src, **safe_details},
                }
            )
        except Exception as exc:
            logger.warning("execution journal operator_release failed err=%s", exc)
        self._maybe_publish_operator_intel_release(
            execution_id=str(execution_id),
            symbol=str(existing.get("symbol") or ""),
            source=str(src),
        )
        return {"ok": True, "release": rel, "execution": existing}

    def list_execution_journal(self, execution_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._repo.list_execution_journal_for_execution(execution_id, limit=limit)

    def handle_signal_event(self, envelope: EventEnvelope) -> dict[str, Any]:
        if self._settings.paper_path_active:
            logger.info(
                "signal event ignored because EXECUTION_MODE=paper event_id=%s",
                envelope.event_id,
            )
            return {
                "decision_action": "ignored",
                "decision_reason": "paper_mode_routes_to_paper_broker",
                "event_id": envelope.event_id,
            }
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        instrument = envelope.instrument.model_dump(mode="json") if envelope.instrument is not None else {}
        signal_leverage = _coerce_optional_int(
            payload.get("execution_leverage_cap") or payload.get("recommended_leverage")
        )
        signal_allowed_leverage = _coerce_optional_int(payload.get("allowed_leverage"))
        trace_body: dict[str, Any] = {
            **envelope.trace,
            "event_id": envelope.event_id,
            "event_type": envelope.event_type,
            "market_family": payload.get("market_family")
            or instrument.get("market_family")
            or self._settings.market_family,
            "signal_trade_action": payload.get("trade_action"),
            "signal_allowed_leverage": signal_allowed_leverage,
            "signal_recommended_leverage": _coerce_optional_int(
                payload.get("recommended_leverage")
            ),
            "signal_execution_leverage_cap": _coerce_optional_int(
                payload.get("execution_leverage_cap")
            ),
            "signal_mirror_leverage": _coerce_optional_int(payload.get("mirror_leverage")),
        }
        if self._settings.live_predatory_passive_maker_default:
            pm0 = trace_body.get("predatory_passive_maker")
            pm0d = dict(pm0) if isinstance(pm0, dict) else {}
            trace_body["predatory_passive_maker"] = {
                **pm0d,
                "enabled": True,
                "source": "live_broker_settings_default",
            }
        sig_pm = payload.get("passive_maker") or payload.get("predatory_passive_maker")
        if isinstance(sig_pm, dict):
            base = trace_body.get("predatory_passive_maker")
            bd = dict(base) if isinstance(base, dict) else {}
            trace_body["predatory_passive_maker"] = {**bd, **sig_pm}
        elif sig_pm is True:
            trace_body["predatory_passive_maker"] = {"enabled": True, "source": "signal_payload"}
        for k in ("orderflow_imbalance_5", "orderflow_imbalance_10", "orderflow_imbalance_20"):
            if k in payload:
                trace_body[k] = payload[k]
        intent = ExecutionIntentRequest(
            source_service="signal-engine",
            signal_id=str(payload.get("signal_id") or envelope.event_id),
            symbol=str(payload.get("symbol") or envelope.symbol or self._settings.symbol),
            market_family=(
                str(
                    payload.get("market_family")
                    or instrument.get("market_family")
                    or self._settings.market_family
                )
            ),
            margin_account_mode=(
                str(
                    payload.get("margin_account_mode")
                    or instrument.get("margin_account_mode")
                    or self._settings.margin_account_mode
                )
            ),
            timeframe=str(payload.get("timeframe") or envelope.timeframe or "").strip() or None,
            direction=cast(Any, str(payload.get("direction") or "neutral").strip().lower()),
            requested_runtime_mode=(
                "live" if self._settings.execution_mode == "live" else "shadow"
            ),
            leverage=signal_leverage,
            approved_7x=bool(payload.get("approved_7x")),
            qty_base=payload.get("qty_base"),
            entry_price=payload.get("entry_price"),
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            note="signal_engine_event",
            payload={
                "signal_payload": payload,
                "event_id": envelope.event_id,
                "event_type": envelope.event_type,
                "instrument": instrument or self._settings.instrument_identity().model_dump(mode="json"),
                "market_family": payload.get("market_family") or instrument.get("market_family") or self._settings.market_family,
                "margin_account_mode": payload.get("margin_account_mode") or instrument.get("margin_account_mode") or self._settings.margin_account_mode,
                "signal_trade_action": payload.get("trade_action"),
                "signal_allowed_leverage": signal_allowed_leverage,
                "signal_recommended_leverage": _coerce_optional_int(
                    payload.get("recommended_leverage")
                ),
                "signal_execution_leverage_cap": _coerce_optional_int(
                    payload.get("execution_leverage_cap")
                ),
                "signal_mirror_leverage": _coerce_optional_int(payload.get("mirror_leverage")),
                "signal_leverage_policy_version": payload.get("leverage_policy_version"),
                "signal_leverage_cap_reasons_json": payload.get("leverage_cap_reasons_json") or [],
            },
            trace=trace_body,
        )
        return self.evaluate_intent(intent, probe_exchange=False)

    def record_paper_reference_event(
        self,
        envelope: EventEnvelope,
        *,
        message_id: str,
    ) -> dict[str, Any]:
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        record = {
            "source_message_id": message_id,
            "dedupe_key": envelope.dedupe_key or f"paper-ref:{message_id}",
            "event_type": envelope.event_type,
            "position_id": str(payload.get("position_id") or ""),
            "symbol": envelope.symbol,
            "state": payload.get("state"),
            "qty_base": payload.get("qty_base"),
            "reason": payload.get("reason"),
            "payload_json": payload,
            "trace_json": envelope.trace,
        }
        saved = self._repo.record_paper_reference_event(record)
        logger.info(
            "paper reference recorded event_type=%s position_id=%s symbol=%s",
            envelope.event_type,
            record["position_id"],
            envelope.symbol,
            extra=log_correlation_fields(
                event_id=envelope.event_id,
                position_id=str(record["position_id"] or "") or None,
                symbol=envelope.symbol,
            ),
        )
        return saved

    def list_recent_decisions(self, limit: int) -> list[dict[str, Any]]:
        return self._repo.list_recent_execution_decisions(limit)

    def list_recent_paper_reference(self, limit: int) -> list[dict[str, Any]]:
        return self._repo.list_recent_paper_reference_events(limit)

    def _effective_runtime_mode(self, requested_mode: str) -> str:
        if requested_mode == "live" and self._settings.execution_mode == "live":
            return "live"
        return "shadow"

    def _decide(
        self,
        intent: ExecutionIntentRequest,
        requested_mode: str,
        effective_mode: str,
        probe: dict[str, Any],
        *,
        exit_preview: dict[str, Any] | None,
        risk_decision: dict[str, Any],
        shadow_path_simulation: bool = False,
        survival_execution_lock: bool = False,
    ) -> tuple[str, str]:
        market_family = str(intent.market_family or self._settings.market_family).strip().lower()
        catalog_entry = self._resolve_catalog_entry(intent)
        if self._catalog is not None and catalog_entry is None:
            return "blocked", "instrument_unknown"
        if self._catalog is not None and not catalog_entry.trading_enabled:
            return "blocked", "instrument_not_tradeable"
        metadata = self._resolve_metadata(intent)
        if self._metadata_service is not None and metadata is not None and not metadata.trading_enabled_now:
            return "blocked", "instrument_session_not_tradeable"
        if intent.symbol not in self._settings.allowed_symbols_set:
            return "blocked", "symbol_not_allowed"
        if market_family not in self._settings.allowed_market_families_set:
            return "blocked", "market_family_not_allowed"
        if (
            market_family == "futures"
            and self._settings.product_type.upper() not in self._settings.allowed_product_types_set
        ):
            return "blocked", "product_type_not_allowed"
        if intent.direction not in ("long", "short"):
            return "blocked", "direction_not_actionable"
        if market_family == "spot" and intent.direction == "short":
            return "blocked", "spot_short_not_supported"
        if survival_execution_lock:
            return "blocked", "survival_execution_lock"
        if risk_decision.get("trade_action") == "do_not_trade":
            return "blocked", str(risk_decision.get("decision_reason") or "shared_risk_blocked")
        if effective_mode == "live":
            sig = self._signal_payload(intent)
            lane_raw = sig.get("meta_trade_lane")
            if lane_raw not in (None, ""):
                lane = str(lane_raw).strip().lower()
                if lane != "candidate_for_live":
                    return "blocked", "meta_trade_lane_not_live_candidate"
            live_blocks = sig.get("live_execution_block_reasons_json")
            if isinstance(live_blocks, list) and any(
                isinstance(x, str) and x.strip() for x in live_blocks
            ):
                return "blocked", "portfolio_live_execution_policy"
        if exit_preview and not exit_preview.get("valid", True):
            reasons = exit_preview.get("reasons") or ["exit_plan_invalid"]
            return "blocked", str(reasons[0])

        if intent.leverage is None or intent.qty_base is None:
            return "blocked", "missing_execution_plan"
        if (
            intent.leverage == 7
            and self._settings.risk_require_7x_approval
            and not intent.approved_7x
        ):
            return "blocked", "missing_7x_approval"
        if not self._settings.live_allow_order_submit:
            return "blocked", "live_submit_disabled"
        if (
            self._settings.live_require_exchange_health
            and probe.get("public_api_ok") is False
        ):
            return "blocked", "exchange_health_unavailable"

        if self._settings.enable_online_drift_block:
            od = self._repo.fetch_online_drift_state()
            if od:
                act = str(od.get("effective_action") or "ok").strip().lower()
                if act == "hard_block":
                    return "blocked", "online_drift_hard_block"
                if act == "shadow_only" and effective_mode == "live":
                    if self._settings.shadow_trade_enable:
                        return "shadow_recorded", "online_drift_live_forced_shadow"
                    return "blocked", "online_drift_shadow_disabled"

        if effective_mode == "shadow":
            if not shadow_path_simulation and not self._settings.shadow_trade_enable:
                return "blocked", "shadow_trade_disabled"
            if requested_mode == "live" and self._settings.execution_mode != "live":
                return "shadow_recorded", "runtime_forced_shadow"
            if self._settings.strategy_execution_mode == "manual":
                return "shadow_recorded", "manual_release_required"
            return "shadow_recorded", "validated_shadow_candidate"

        if not self._settings.live_trade_enable:
            return "blocked", "live_trade_disabled"
        try:
            if self._repo.safety_latch_is_active():
                return "blocked", "live_safety_latch_active"
        except Exception as exc:
            logger.warning("safety_latch_is_active in decide failed: %s", exc)
        ok_truth, truth_reason = self._live_exchange_truth_allows_submit()
        if not ok_truth:
            return "blocked", truth_reason
        if probe.get("private_api_configured") is False:
            return "blocked", "private_api_not_configured"
        if self._settings.strategy_execution_mode == "manual":
            return "live_candidate_recorded", "manual_release_required"
        return "live_candidate_recorded", "validated_live_candidate"

    def _signal_payload(self, intent: ExecutionIntentRequest) -> dict[str, Any]:
        nested = intent.payload.get("signal_payload")
        if isinstance(nested, dict):
            return dict(nested)
        return dict(intent.payload)

    def _exit_preview(self, intent: ExecutionIntentRequest) -> dict[str, Any] | None:
        entry_price = Decimal(str(intent.entry_price)) if intent.entry_price else Decimal("0")
        stop_loss = Decimal(str(intent.stop_loss)) if intent.stop_loss else Decimal("0")
        take_profit = Decimal(str(intent.take_profit)) if intent.take_profit else Decimal("0")
        qty_base = Decimal(str(intent.qty_base)) if intent.qty_base else Decimal("0")
        if intent.direction not in ("long", "short") or entry_price <= 0 or qty_base <= 0:
            return None
        if stop_loss <= 0 and take_profit <= 0:
            return None
        trace = self._signal_payload(intent)
        hints = extract_exit_execution_hints_from_trace(trace)
        ov = merge_exit_build_overrides(
            take_pcts=(
                Decimal(str(self._settings.tp1_pct)),
                Decimal(str(self._settings.tp2_pct)),
                Decimal(str(self._settings.tp3_pct)),
            ),
            runner_enabled=bool(self._settings.exit_runner_enabled),
            runner_trail_mult=Decimal(str(self._settings.runner_trail_atr_mult)),
            break_even_after_tp_index=int(self._settings.exit_break_even_after_tp_index),
            hints=hints,
        )
        stop_plan, tp_plan = build_live_exit_plans(
            side=intent.direction,
            entry_price=entry_price,
            initial_qty=qty_base,
            stop_loss=stop_loss if stop_loss > 0 else None,
            take_profit=take_profit if take_profit > 0 else None,
            stop_trigger_type=self._settings.stop_trigger_type_default,
            tp_trigger_type=self._settings.tp_trigger_type_default,
            take_pcts=ov["take_pcts"],
            runner_enabled=ov["runner_enabled"],
            runner_trail_mult=ov["runner_trail_mult"],
            break_even_after_tp_index=ov["break_even_after_tp_index"],
            timeframe=intent.timeframe,
            runner_arm_after_tp_index=int(ov["runner_arm_after_tp_index"]),
        )
        allowed_leverage = _coerce_optional_int(
            intent.payload.get("signal_allowed_leverage")
            or intent.payload.get("allowed_leverage")
        )
        metadata = self._resolve_metadata(intent)
        metadata_ctx = (
            self._metadata_service.exit_validation_context(
                metadata=metadata,
                entry_price=entry_price,
            )
            if self._metadata_service is not None and metadata is not None
            else {}
        )
        validation = validate_exit_plan(
            side=intent.direction,
            entry_price=entry_price,
            stop_plan=stop_plan,
            tp_plan=tp_plan,
            leverage=Decimal(str(intent.leverage)) if intent.leverage is not None else None,
            allowed_leverage=allowed_leverage,
            max_position_risk_pct=self._settings.risk_max_position_risk_pct,
            risk_trade_action=_opt_text_from_payload(intent.payload, "signal_trade_action"),
            market_family=str(intent.market_family or self._settings.market_family),
            **metadata_ctx,
        )
        return {
            "valid": validation["valid"],
            "reasons": validation["reasons"],
            "metrics": validation["metrics"],
            "stop_plan": validation["stop_plan"],
            "tp_plan": validation["tp_plan"],
        }

    def _resolve_catalog_entry(
        self,
        intent: ExecutionIntentRequest,
    ):
        if self._catalog is None:
            return self._settings.instrument_identity()
        try:
            family = str(intent.market_family or self._settings.market_family)
            return self._catalog.resolve(
                symbol=intent.symbol,
                market_family=family,
                product_type=(self._settings.product_type if family == "futures" else None),
                margin_account_mode=(
                    str(intent.margin_account_mode or self._settings.margin_account_mode)
                    if family == "margin"
                    else None
                ),
                refresh_if_missing=False,
            )
        except UnknownInstrumentError:
            return None

    def _resolve_metadata(self, intent: ExecutionIntentRequest):
        if self._metadata_service is None:
            return None
        try:
            family = str(intent.market_family or self._settings.market_family)
            return self._metadata_service.resolve_metadata(
                symbol=intent.symbol,
                market_family=family,
                product_type=(self._settings.product_type if family == "futures" else None),
                margin_account_mode=(
                    str(intent.margin_account_mode or self._settings.margin_account_mode)
                    if family == "margin"
                    else None
                ),
                refresh_if_missing=False,
            )
        except UnknownInstrumentError:
            return None
