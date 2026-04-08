"""Publiziert strukturierte Operator-Intel-Events (Telegram-Outbox via alert-engine)."""

from __future__ import annotations

import json
import logging
from typing import Any

from shared_py.eventbus import EventEnvelope, RedisStreamBus, STREAM_OPERATOR_INTEL
from shared_py.operator_intel import build_operator_intel_envelope_payload

logger = logging.getLogger("signal_engine.operator_intel")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            return dict(json.loads(value))
        except json.JSONDecodeError:
            return {}
    return {}


def build_signal_operator_intel_payload(bundle: dict[str, Any]) -> dict[str, Any] | None:
    ep = bundle.get("event_payload")
    db = bundle.get("db_row")
    if not isinstance(ep, dict) or not isinstance(db, dict):
        return None
    signal_id = str(ep.get("signal_id") or "")
    if not signal_id:
        return None
    symbol = str(ep.get("symbol") or "")
    trade_action = str(ep.get("trade_action") or db.get("trade_action") or "").strip().lower()
    rj = _as_dict(db.get("reasons_json"))
    spec = rj.get("specialists") if isinstance(rj.get("specialists"), dict) else {}
    router = spec.get("router_arbitration") if isinstance(spec.get("router_arbitration"), dict) else {}
    router_id = str(router.get("router_id") or "").strip()
    routed_action = str(
        router.get("selected_trade_action") or router.get("pre_adversary_trade_action") or ""
    ).strip()
    specialist_route = " / ".join(part for part in (router_id, routed_action) if part)
    playbook_id = str(ep.get("playbook_id") or db.get("playbook_id") or "") or None
    regime = str(ep.get("market_regime") or db.get("market_regime") or "") or None
    exit_families: list[str] = []
    pb = spec.get("playbook") if isinstance(spec.get("playbook"), dict) else {}
    if isinstance(pb.get("exit_families"), list):
        exit_families = [str(x) for x in pb["exit_families"][:6]]
    stop_exit_family = ", ".join(exit_families) if exit_families else None

    allowed = ep.get("allowed_leverage")
    rec = ep.get("recommended_leverage") or ep.get("execution_leverage_cap")
    leverage_band = None
    if allowed is not None or rec is not None:
        leverage_band = f"allowed={allowed} cap={rec}"

    reasons: list[str] = []
    rr = ep.get("rejection_reasons_json") or db.get("rejection_reasons_json")
    if isinstance(rr, list):
        reasons.extend(str(x) for x in rr[:8])
    ar = ep.get("abstention_reasons_json")
    if isinstance(ar, list):
        reasons.extend(str(x) for x in ar[:6])
    if isinstance(router.get("router_reasons"), list):
        reasons.extend(str(x) for x in router["router_reasons"][:6])
    dcf = rj.get("decision_control_flow") if isinstance(rj.get("decision_control_flow"), dict) else {}
    no_trade = dcf.get("no_trade_path") if isinstance(dcf.get("no_trade_path"), dict) else {}
    if isinstance(no_trade.get("phase_block_drivers"), list):
        reasons.extend(str(x) for x in no_trade["phase_block_drivers"][:6])

    decision_state = str(ep.get("decision_state") or db.get("decision_state") or "")
    risk_summary = f"decision_state={decision_state} risk_score={ep.get('risk_score_0_100')}"
    stop_fragility = ep.get("stop_fragility_0_1") or db.get("stop_fragility_0_1")
    stop_exec = ep.get("stop_executability_0_1") or db.get("stop_executability_0_1")
    if stop_fragility is not None or stop_exec is not None:
        risk_summary = (
            f"{risk_summary} stop_fragility={stop_fragility} stop_exec={stop_exec}"
        )[:240]
    if trade_action == "do_not_trade":
        intel_kind = "no_trade"
        severity = "warn"
        outcome = "no_trade"
        dedupe_ttl = 15
    else:
        intel_kind = "strategy_intent"
        severity = "info" if str(ep.get("signal_class") or "").lower() != "gross" else "warn"
        outcome = f"allow_trade class={ep.get('signal_class')}"
        dedupe_ttl = 5

    dedupe_key = f"opintel:signal:{signal_id}:{intel_kind}"

    return build_operator_intel_envelope_payload(
        intel_kind=intel_kind,
        symbol=symbol,
        correlation_id=f"sig:{signal_id}",
        market_family=(str(ep.get("market_family") or "").strip() or None),
        playbook_id=playbook_id,
        specialist_route=specialist_route or None,
        regime=regime,
        risk_summary=risk_summary[:240],
        stop_exit_family=stop_exit_family,
        leverage_band=leverage_band,
        reasons=reasons[:12] or None,
        outcome=outcome,
        signal_id=signal_id,
        severity=severity,
        dedupe_key=dedupe_key,
        dedupe_ttl_minutes=dedupe_ttl,
    )


def publish_signal_operator_intel(
    bus: RedisStreamBus,
    bundle: dict[str, Any],
    *,
    logger_: logging.Logger | None = None,
) -> str | None:
    log = logger_ or logger
    pl = build_signal_operator_intel_payload(bundle)
    if pl is None:
        return None
    ep = bundle.get("event_payload")
    instrument = _as_dict((ep or {}).get("instrument"))
    symbol = str((ep or {}).get("symbol") or instrument.get("symbol") or "").strip().upper()
    env = EventEnvelope(
        event_type="operator_intel",
        symbol=symbol,
        timeframe=str((ep or {}).get("timeframe") or "") or None,
        dedupe_key=str(pl.get("dedupe_key") or ""),
        payload=pl,
        trace={"source": "signal-engine"},
    )
    mid = bus.publish(STREAM_OPERATOR_INTEL, env)
    log.info("published operator_intel signal_id=%s kind=%s", ep.get("signal_id"), pl.get("intel_kind"))
    return str(mid)
