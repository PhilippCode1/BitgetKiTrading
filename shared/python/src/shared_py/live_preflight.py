from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

GateStatus = Literal["pass", "warn", "fail", "unknown", "missing", "stale"]


@dataclass(frozen=True)
class LivePreflightContext:
    execution_mode_live: bool
    live_trade_enable: bool
    owner_approved: bool
    asset_in_catalog: bool
    asset_status_ok: bool
    asset_live_allowed: bool
    instrument_contract_complete: bool
    instrument_metadata_fresh: bool
    data_quality_status: GateStatus
    liquidity_status: GateStatus
    slippage_ok: bool
    risk_tier_live_allowed: bool
    order_sizing_ok: bool
    portfolio_risk_ok: bool
    strategy_evidence_ok: bool
    bitget_readiness_ok: bool
    reconcile_ok: bool
    kill_switch_active: bool
    safety_latch_active: bool
    unknown_order_state: bool
    account_snapshot_fresh: bool
    idempotency_key: str | None
    audit_context_present: bool
    warning_policy_allows_live: dict[str, bool] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    liquidity_gate_present: bool = True
    spread_gate_present: bool = True
    slippage_gate_present: bool = True
    orderbook_present: bool = True
    orderbook_fresh: bool = True
    market_order_slippage_checked: bool = True
    stop_tp_executable: bool = True
    recovery_latch_active: bool = False
    recovery_reconcile_required: bool = False
    recovery_exchange_truth_required: bool = False
    recovery_operator_review_required: bool = False
    redis_state_known: bool = True
    event_state_known: bool = True


@dataclass(frozen=True)
class LivePreflightDecision:
    passed: bool
    blocking_reasons: list[str]
    warning_reasons: list[str]
    missing_gates: list[str]
    checked_at: str
    submit_allowed: bool


_DE_REASON = {
    "execution_mode_not_live": "Ausfuehrungsmodus ist nicht live.",
    "live_trade_enable_false": "LIVE_TRADE_ENABLE ist nicht aktiv.",
    "owner_approval_missing": "Owner-Freigabe von Philipp fehlt.",
    "asset_not_in_catalog": "Asset ist nicht im Katalog vorhanden.",
    "asset_status_not_ok": "Asset ist delisted, suspended oder unknown.",
    "asset_not_live_allowed": "Asset ist nicht live freigegeben.",
    "instrument_contract_missing": "Instrument-Order-Contract ist unvollstaendig.",
    "instrument_metadata_stale": "Instrument-Metadaten sind stale.",
    "data_quality_not_pass": "Datenqualitaet ist nicht livefaehig.",
    "liquidity_not_pass": "Liquiditaet ist nicht ausreichend.",
    "slippage_too_high": "Slippage liegt ueber der Schwelle.",
    "risk_tier_not_live_allowed": "Risk-Tier erlaubt kein Live-Opening.",
    "order_sizing_not_safe": "Order-Sizing ist nicht sicher.",
    "portfolio_risk_not_safe": "Portfolio-Risk ist nicht sicher.",
    "strategy_evidence_missing_or_invalid": "Strategie-Evidence fehlt oder passt nicht.",
    "bitget_readiness_not_ok": "Bitget-Readiness ist nicht OK.",
    "reconcile_not_ok": "Reconcile ist nicht OK.",
    "kill_switch_active": "Kill-Switch ist aktiv.",
    "safety_latch_active": "Safety-Latch ist aktiv.",
    "unknown_order_state_active": "Unklarer Order-State ist aktiv.",
    "account_snapshot_stale": "Account-Snapshot ist stale oder fehlt.",
    "idempotency_key_missing": "Idempotency-Key fehlt.",
    "audit_context_missing": "Audit-Context fehlt.",
    "liquidity_gate_missing": "Liquidity-Gate fehlt.",
    "spread_gate_missing": "Spread-Gate fehlt.",
    "slippage_gate_missing": "Slippage-Gate fehlt.",
    "orderbook_missing": "Orderbook fehlt.",
    "orderbook_stale": "Orderbook ist stale.",
    "market_order_slippage_gate_missing": "Market-Order ohne Slippage-Gate ist nicht erlaubt.",
    "stop_tp_not_executable": "Stop/TP ist unter Mikrostrukturregeln nicht ausfuehrbar.",
    "recovery_latch_active": "Recovery-Latch ist aktiv.",
    "recovery_reconcile_required": "Recovery verlangt Reconcile vor Live.",
    "recovery_exchange_truth_required": "Recovery verlangt Exchange-Truth vor Live.",
    "recovery_operator_review_required": "Recovery verlangt Operator-Review vor Live.",
    "redis_state_unknown": "Redis-State ist unbekannt.",
    "event_state_unknown": "Event-State ist unbekannt.",
}


def evaluate_live_preflight(context: LivePreflightContext) -> LivePreflightDecision:
    blocking: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    def block(reason: str) -> None:
        if reason not in blocking:
            blocking.append(reason)

    if not context.execution_mode_live:
        block("execution_mode_not_live")
    if not context.live_trade_enable:
        block("live_trade_enable_false")
    if not context.owner_approved:
        block("owner_approval_missing")
    if not context.asset_in_catalog:
        block("asset_not_in_catalog")
    if not context.asset_status_ok:
        block("asset_status_not_ok")
    if not context.asset_live_allowed:
        block("asset_not_live_allowed")
    if not context.instrument_contract_complete:
        block("instrument_contract_missing")
    if not context.instrument_metadata_fresh:
        block("instrument_metadata_stale")

    for gate_name, gate_value, fail_reason in (
        ("data_quality", context.data_quality_status, "data_quality_not_pass"),
        ("liquidity", context.liquidity_status, "liquidity_not_pass"),
    ):
        if gate_value in {"missing", "unknown", "stale"}:
            missing.append(gate_name)
            block(fail_reason)
            continue
        if gate_value == "fail":
            block(fail_reason)
            continue
        if gate_value == "warn":
            warnings.append(gate_name)
            if not context.warning_policy_allows_live.get(gate_name, False):
                block(fail_reason)

    if not context.slippage_ok:
        block("slippage_too_high")
    if not context.risk_tier_live_allowed:
        block("risk_tier_not_live_allowed")
    if not context.order_sizing_ok:
        block("order_sizing_not_safe")
    if not context.portfolio_risk_ok:
        block("portfolio_risk_not_safe")
    if not context.strategy_evidence_ok:
        block("strategy_evidence_missing_or_invalid")
    if not context.bitget_readiness_ok:
        block("bitget_readiness_not_ok")
    if not context.reconcile_ok:
        block("reconcile_not_ok")
    if context.kill_switch_active:
        block("kill_switch_active")
    if context.safety_latch_active:
        block("safety_latch_active")
    if context.unknown_order_state:
        block("unknown_order_state_active")
    if not context.account_snapshot_fresh:
        block("account_snapshot_stale")
    if not context.idempotency_key:
        block("idempotency_key_missing")
    if not context.audit_context_present:
        block("audit_context_missing")
    if not context.liquidity_gate_present:
        block("liquidity_gate_missing")
    if not context.spread_gate_present:
        block("spread_gate_missing")
    if not context.slippage_gate_present:
        block("slippage_gate_missing")
    if not context.orderbook_present:
        block("orderbook_missing")
    if not context.orderbook_fresh:
        block("orderbook_stale")
    if not context.market_order_slippage_checked:
        block("market_order_slippage_gate_missing")
    if not context.stop_tp_executable:
        block("stop_tp_not_executable")
    if context.recovery_latch_active:
        block("recovery_latch_active")
    if context.recovery_reconcile_required:
        block("recovery_reconcile_required")
    if context.recovery_exchange_truth_required:
        block("recovery_exchange_truth_required")
    if context.recovery_operator_review_required:
        block("recovery_operator_review_required")
    if not context.redis_state_known:
        block("redis_state_unknown")
    if not context.event_state_known:
        block("event_state_unknown")

    passed = len(blocking) == 0
    return LivePreflightDecision(
        passed=passed,
        blocking_reasons=blocking,
        warning_reasons=list(dict.fromkeys(warnings)),
        missing_gates=list(dict.fromkeys(missing)),
        checked_at=context.checked_at,
        submit_allowed=passed,
    )


def live_preflight_blocks_submit(decision: LivePreflightDecision) -> bool:
    return not decision.submit_allowed


def build_live_preflight_reasons_de(decision: LivePreflightDecision) -> list[str]:
    if not decision.blocking_reasons:
        return ["Preflight erfolgreich: alle Pflicht-Gates sind gruen."]
    return [_DE_REASON.get(code, f"Unbekannter Blockgrund: {code}") for code in decision.blocking_reasons]


def build_live_preflight_audit_payload(
    *,
    context: LivePreflightContext,
    decision: LivePreflightDecision,
) -> dict[str, object]:
    return {
        "checked_at": decision.checked_at,
        "passed": decision.passed,
        "submit_allowed": decision.submit_allowed,
        "blocking_reasons": decision.blocking_reasons,
        "warning_reasons": decision.warning_reasons,
        "missing_gates": decision.missing_gates,
        "context_flags": {
            "execution_mode_live": context.execution_mode_live,
            "live_trade_enable": context.live_trade_enable,
            "owner_approved": context.owner_approved,
            "asset_in_catalog": context.asset_in_catalog,
            "asset_status_ok": context.asset_status_ok,
            "asset_live_allowed": context.asset_live_allowed,
            "instrument_contract_complete": context.instrument_contract_complete,
            "instrument_metadata_fresh": context.instrument_metadata_fresh,
            "data_quality_status": context.data_quality_status,
            "liquidity_status": context.liquidity_status,
            "slippage_ok": context.slippage_ok,
            "risk_tier_live_allowed": context.risk_tier_live_allowed,
            "order_sizing_ok": context.order_sizing_ok,
            "portfolio_risk_ok": context.portfolio_risk_ok,
            "strategy_evidence_ok": context.strategy_evidence_ok,
            "bitget_readiness_ok": context.bitget_readiness_ok,
            "reconcile_ok": context.reconcile_ok,
            "kill_switch_active": context.kill_switch_active,
            "safety_latch_active": context.safety_latch_active,
            "unknown_order_state": context.unknown_order_state,
            "account_snapshot_fresh": context.account_snapshot_fresh,
            "idempotency_present": bool(context.idempotency_key),
            "audit_context_present": context.audit_context_present,
            "liquidity_gate_present": context.liquidity_gate_present,
            "spread_gate_present": context.spread_gate_present,
            "slippage_gate_present": context.slippage_gate_present,
            "orderbook_present": context.orderbook_present,
            "orderbook_fresh": context.orderbook_fresh,
            "market_order_slippage_checked": context.market_order_slippage_checked,
            "stop_tp_executable": context.stop_tp_executable,
            "recovery_latch_active": context.recovery_latch_active,
            "recovery_reconcile_required": context.recovery_reconcile_required,
            "recovery_exchange_truth_required": context.recovery_exchange_truth_required,
            "recovery_operator_review_required": context.recovery_operator_review_required,
            "redis_state_known": context.redis_state_known,
            "event_state_known": context.event_state_known,
        },
    }
