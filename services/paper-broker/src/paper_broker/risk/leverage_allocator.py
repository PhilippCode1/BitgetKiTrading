from __future__ import annotations

import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from paper_broker.config import PaperBrokerSettings
from paper_broker.engine.liquidation import should_liquidate_approx
from paper_broker.risk.common_risk import build_paper_account_risk_metrics
from paper_broker.risk.plan_service import build_auto_plan_bundle
from shared_py.leverage_allocator import MAX_LEVERAGE, allocate_integer_leverage
from shared_py.unified_leverage_allocator import extract_execution_leverage_cap_from_signal_row


def allocate_paper_execution_leverage(
    conn: psycopg.Connection[Any],
    *,
    settings: PaperBrokerSettings,
    account_row: dict[str, Any],
    tenant_id: str,
    contract_max_leverage: int,
    requested_leverage: Decimal,
    signal_payload: dict[str, Any] | None,
    symbol: str,
    side: str,
    qty_base: Decimal,
    entry_price: Decimal,
    entry_fee_usdt: Decimal,
    timeframe: str | None,
    instrument_metadata: dict[str, Any] | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    metadata_entry = {}
    metadata_session = {}
    if isinstance(instrument_metadata, dict):
        if isinstance(instrument_metadata.get("entry"), dict):
            metadata_entry = instrument_metadata.get("entry") or {}
            metadata_session = (
                instrument_metadata.get("session_state")
                if isinstance(instrument_metadata.get("session_state"), dict)
                else {}
            )
        else:
            metadata_entry = instrument_metadata
    risk_max = min(
        int(contract_max_leverage),
        int(settings.paper_max_leverage),
        int(settings.risk_allowed_leverage_max),
        MAX_LEVERAGE,
    )
    if metadata_entry.get("leverage_max") not in (None, ""):
        try:
            risk_max = min(risk_max, int(metadata_entry["leverage_max"]))
        except (TypeError, ValueError):
            pass
    caps = {
        "exchange_cap": risk_max,
        "model_cap": _signal_model_cap(signal_payload, requested_leverage=requested_leverage, fallback=risk_max),
    }
    exec_cap = extract_execution_leverage_cap_from_signal_row(signal_payload or {})
    if exec_cap is not None and exec_cap >= 0:
        caps["signal_execution_leverage_cap"] = min(risk_max, int(exec_cap))
    if metadata_entry and not bool(metadata_entry.get("supports_leverage", True)):
        caps["instrument_leverage_cap"] = 0
    if metadata_session and metadata_session.get("trade_allowed_now") is False:
        caps["instrument_session_cap"] = 0
    audit: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "timeframe": timeframe,
        "instrument_metadata": instrument_metadata or {},
    }

    preview = _preview_stop_bundle(
        conn,
        settings=settings,
        symbol=symbol,
        side=side,
        qty_base=qty_base,
        entry_price=entry_price,
        timeframe=timeframe,
    )
    audit.update(preview)
    if preview["stop_distance_bps"] is not None:
        caps["stop_distance_cap"] = _stop_distance_cap(
            settings=settings,
            stop_distance_bps=preview["stop_distance_bps"],
            risk_max=risk_max,
        )
    if preview["stop_price"] is not None:
        caps["liquidation_buffer_cap"] = _liquidation_buffer_cap(
            settings=settings,
            risk_max=risk_max,
            qty_base=qty_base,
            entry_price=entry_price,
            stop_price=preview["stop_price"],
            side=side,
            entry_fee_usdt=entry_fee_usdt,
        )

    projected_margin = (qty_base * entry_price) / max(requested_leverage, Decimal("1"))
    tid = str(tenant_id).strip() or "default"
    metrics = build_paper_account_risk_metrics(
        conn,
        account_id=UUID(str(account_row.get("account_id"))),
        tenant_id=tid,
        account_row=account_row,
        now_ms=now_ms if now_ms is not None else int(time.time() * 1000),
        projected_margin=projected_margin,
    )
    projected_margin_usage_pct = float(metrics.get("projected_margin_usage_pct") or 0.0)
    drawdown_pct = float(metrics.get("account_drawdown_pct") or 0.0)
    audit["projected_margin_usage_pct"] = round(projected_margin_usage_pct, 6)
    audit["drawdown_pct"] = round(drawdown_pct, 6)
    caps["margin_usage_cap"] = _ratio_cap(
        ratio=projected_margin_usage_pct,
        hard_limit=float(settings.leverage_max_margin_usage_pct),
        risk_max=risk_max,
    )
    caps["drawdown_cap"] = _ratio_cap(
        ratio=drawdown_pct,
        hard_limit=float(settings.risk_max_account_drawdown_pct),
        risk_max=risk_max,
    )

    decision = allocate_integer_leverage(
        requested_leverage=requested_leverage,
        caps=caps,
        min_leverage=settings.risk_allowed_leverage_min,
        max_leverage=risk_max,
        blocked_reason="paper_allowed_leverage_below_minimum",
    )
    decision["caps"] = {name: int(value) for name, value in caps.items()}
    decision["audit"] = _json_safe(audit)
    return decision


def _signal_model_cap(
    signal_payload: dict[str, Any] | None,
    *,
    requested_leverage: Decimal,
    fallback: int,
) -> int:
    if not signal_payload:
        return min(int(requested_leverage), fallback)
    trade_action = str(signal_payload.get("trade_action") or "").strip().lower()
    if trade_action == "do_not_trade":
        return 0
    for field in ("allowed_leverage", "recommended_leverage"):
        value = signal_payload.get(field)
        if value in (None, ""):
            continue
        try:
            return max(0, min(fallback, int(value)))
        except (TypeError, ValueError):
            continue
    return min(int(requested_leverage), fallback)


def _preview_stop_bundle(
    conn: psycopg.Connection[Any],
    *,
    settings: PaperBrokerSettings,
    symbol: str,
    side: str,
    qty_base: Decimal,
    entry_price: Decimal,
    timeframe: str | None,
) -> dict[str, Any]:
    if not timeframe:
        return {
            "stop_price": None,
            "stop_distance_bps": None,
            "stop_quality_score": None,
            "stop_plan_preview": None,
        }
    try:
        stop_plan, _tp_plan, stop_quality_score, _rr_s = build_auto_plan_bundle(
            conn,
            position_row={
                "symbol": symbol,
                "side": side,
                "qty_base": qty_base,
                "entry_price_avg": entry_price,
            },
            settings=settings,
            timeframe=timeframe,
            preferred_stop_trigger=settings.stop_trigger_type_default,
            method_mix=None,
        )
        stop_price = _dec(stop_plan.get("stop_price"))
        if stop_price <= 0:
            return {
                "stop_price": None,
                "stop_distance_bps": None,
                "stop_quality_score": stop_quality_score,
                "stop_plan_preview": stop_plan,
            }
        stop_distance_bps = float((abs(entry_price - stop_price) / entry_price) * Decimal("10000"))
        return {
            "stop_price": stop_price,
            "stop_distance_bps": round(stop_distance_bps, 6),
            "stop_quality_score": int(stop_quality_score),
            "stop_plan_preview": stop_plan,
        }
    except Exception:
        return {
            "stop_price": None,
            "stop_distance_bps": None,
            "stop_quality_score": None,
            "stop_plan_preview": None,
        }


def _stop_distance_cap(
    *,
    settings: PaperBrokerSettings,
    stop_distance_bps: float,
    risk_max: int,
) -> int:
    if stop_distance_bps <= 0:
        return 0
    raw_cap = int(Decimal(str(settings.leverage_stop_distance_scale_bps)) / Decimal(str(stop_distance_bps)))
    return max(0, min(risk_max, raw_cap))


def _liquidation_buffer_cap(
    *,
    settings: PaperBrokerSettings,
    risk_max: int,
    qty_base: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    side: str,
    entry_fee_usdt: Decimal,
) -> int:
    min_buffer_bps = Decimal(str(settings.leverage_min_liquidation_buffer_bps))
    if side == "long":
        stress_mark = stop_price * (Decimal("1") - (min_buffer_bps / Decimal("10000")))
    else:
        stress_mark = stop_price * (Decimal("1") + (min_buffer_bps / Decimal("10000")))
    notional = abs(qty_base * entry_price)
    for leverage in range(risk_max, settings.risk_allowed_leverage_min - 1, -1):
        isolated_margin = notional / Decimal(str(leverage))
        if not should_liquidate_approx(
            isolated_margin=isolated_margin,
            qty=qty_base,
            entry_avg=entry_price,
            mark=stress_mark,
            side=side,
            accrued_fees=entry_fee_usdt,
            net_funding_ledger=Decimal("0"),
            maintenance_margin_rate=Decimal(str(settings.paper_mmr_base)),
            liq_fee_buffer_usdt=Decimal(str(settings.paper_liq_fee_buffer_usdt)),
        ):
            return leverage
    return 0


def _ratio_cap(*, ratio: float, hard_limit: float, risk_max: int) -> int:
    if hard_limit <= 0:
        return 0
    if ratio >= hard_limit:
        return 0
    remaining = max(0.0, 1.0 - (ratio / hard_limit))
    return max(0, min(risk_max, 6 + int(round((risk_max - 6) * remaining))))


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
