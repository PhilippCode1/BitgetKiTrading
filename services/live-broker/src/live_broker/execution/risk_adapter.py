from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from shared_py.inference_governance import live_broker_payload_inference_blocks_trading
from shared_py.observability.vpin_redis import (
    VPIN_HARD_HALT_THRESHOLD_0_1,
    VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1,
)
from shared_py.resilience.survival_kernel import (
    effective_portfolio_exposure_limit_pct,
    portfolio_diversification_risk_buffer_0_1,
)
from shared_py.risk_engine import (
    RISK_ENGINE_POLICY_VERSION,
    build_trade_risk_limits,
    compute_drawdown_from_points,
    compute_margin_usage_pct,
    compute_position_risk_pct,
    evaluate_trade_risk,
)

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings
    from live_broker.execution.models import ExecutionIntentRequest
    from live_broker.persistence.repo import LiveBrokerRepository

_DAY_MS = 86_400_000
_WEEK_MS = 7 * _DAY_MS
_ACCOUNT_EQUITY_FIELDS = (
    "equity",
    "accountEquity",
    "usdtEquity",
    "marginBalance",
)
_ACCOUNT_AVAILABLE_FIELDS = (
    "available",
    "availableBalance",
    "maxOpenPosAvailable",
    "free",
)
_POSITION_MARGIN_FIELDS = (
    "margin",
    "marginSize",
    "marginAmount",
    "marginUsed",
    "marginNum",
)
_POSITION_SIZE_FIELDS = (
    "total",
    "available",
    "holdVol",
    "openDelegateSize",
)

PORTFOLIO_EXPOSURE_EXCEEDED = "PORTFOLIO_EXPOSURE_EXCEEDED"
INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
RISK_VPIN_HALT = "RISK_VPIN_HALT"


def _raw_json_dict(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw_json")
    if isinstance(raw, dict):
        return raw
    return {}


def _leverage_from_position_row(row: dict[str, Any]) -> int:
    raw = _raw_json_dict(row)
    for key in ("leverage", "openLeverage", "open_leverage", "posLeverage"):
        v = raw.get(key) or row.get(key)
        if v in (None, ""):
            continue
        try:
            lv = int(Decimal(str(v)))
            if lv > 0:
                return lv
        except (InvalidOperation, TypeError, ValueError):
            continue
    return 1


def _is_live_position_open(row: dict[str, Any]) -> bool:
    return abs(_dec(row.get("size_base"))) > 0


def _position_notional_leveraged_usdt(row: dict[str, Any]) -> Decimal:
    nvl = _dec(row.get("notional_value"))
    if nvl > 0:
        return nvl
    sz = abs(_dec(row.get("size_base")))
    ep = _dec(row.get("entry_price"))
    if sz <= 0 or ep <= 0:
        return Decimal("0")
    lev = _leverage_from_position_row(row)
    return sz * ep * Decimal(str(lev))


def _intent_opening_increase_exposure(intent: ExecutionIntentRequest) -> bool:
    if bool(intent.payload.get("reduce_only")):
        return False
    if str(intent.payload.get("order_action") or "").strip().lower() == "reduce":
        return False
    return True


def _distinct_instruments_for_portfolio(
    open_rows: list[dict[str, Any]],
    intent_symbol: str,
) -> int:
    insts = {str(r.get("inst_id") or "").strip().upper() for r in open_rows if _is_live_position_open(r)}
    s = str(intent_symbol or "").strip().upper()
    if s:
        insts.add(s)
    return max(1, len(insts) if insts else 1)


def _proposed_open_notional_usdt(intent: ExecutionIntentRequest) -> Decimal:
    if not _intent_opening_increase_exposure(intent):
        return Decimal("0")
    lev = int(intent.leverage or 0)
    if lev <= 0:
        return Decimal("0")
    qty = _dec(intent.qty_base)
    entry = _dec(intent.entry_price)
    if qty <= 0 or entry <= 0:
        return Decimal("0")
    return qty * entry * Decimal(str(lev))


def assert_portfolio_exposure_limit(
    *,
    settings: LiveBrokerSettings,
    repo: LiveBrokerRepository,
    intent: ExecutionIntentRequest,
    total_equity: Decimal,
) -> tuple[bool, dict[str, Any]]:
    """
    True, wenn Summe(Notional offene DB-Positionen) + geplante Eroeffnung
    die effektive Portfoliogrenze (Equity * Limit, Surival-Buffer bei vielen Instrumenten) nicht uebersteigt.
    """
    detail: dict[str, Any] = {
        "active": bool(_intent_opening_increase_exposure(intent) and int(intent.leverage or 0) > 0),
    }
    if not detail["active"] or total_equity <= 0:
        return True, detail

    rows = (
        repo.list_live_positions() if hasattr(repo, "list_live_positions") else []  # type: ignore[union-attr]
    )
    if not isinstance(rows, list):
        rows = []
    open_rows = [r for r in rows if isinstance(r, dict) and _is_live_position_open(r)]
    existing = sum((_position_notional_leveraged_usdt(r) for r in open_rows), start=Decimal("0"))
    proposed = _proposed_open_notional_usdt(intent)
    distinct = _distinct_instruments_for_portfolio(open_rows, intent.symbol)
    buffer_pi = float(getattr(settings, "risk_portfolio_diversification_buffer_per_instrument", 0.05))
    base = float(getattr(settings, "risk_max_portfolio_exposure_pct", 0.25))
    buf = portfolio_diversification_risk_buffer_0_1(
        distinct_instruments=distinct,
        buffer_per_instrument=buffer_pi,
    )
    eff_pct = effective_portfolio_exposure_limit_pct(
        base_limit_pct=base,
        distinct_instruments=distinct,
        buffer_per_instrument=buffer_pi,
    )
    cap = total_equity * Decimal(str(eff_pct))
    total_exp = existing + proposed
    ok = total_exp <= cap
    detail.update(
        {
            "distinct_instruments": distinct,
            "portfolio_diversification_buffer_0_1": buf,
            "base_exposure_limit_pct": base,
            "effective_exposure_limit_pct": eff_pct,
            "total_equity_usdt": _decimal_json(total_equity),
            "exposure_cap_usdt": _decimal_json(cap),
            "existing_exposure_notional_usdt": _decimal_json(existing),
            "proposed_exposure_notional_usdt": _decimal_json(proposed),
            "total_exposure_notional_usdt": _decimal_json(total_exp),
        }
    )
    return ok, detail


def _portfolio_rejected_risk_shape(
    *,
    limits: Any,
    signal_payload: dict[str, Any],
    metrics: dict[str, Any],
    portfolio_detail: dict[str, Any],
    position_notional: Decimal | None,
    projected_margin_usage_pct: float | None,
    position_risk_pct: float | None,
) -> dict[str, Any]:
    return {
        "policy_version": RISK_ENGINE_POLICY_VERSION,
        "trade_action": "do_not_trade",
        "decision_state": "rejected",
        "decision_reason": PORTFOLIO_EXPOSURE_EXCEEDED,
        "reasons_json": [PORTFOLIO_EXPOSURE_EXCEEDED],
        "signal_reasons_json": [],
        "market_reasons_json": [PORTFOLIO_EXPOSURE_EXCEEDED],
        "account_reasons_json": [],
        "position_reasons_json": [],
        "limits": asdict(limits) if limits is not None else {},
        "metrics": {
            "open_positions_count": metrics.get("open_positions_count"),
            "position_notional_usdt": _decimal_json(position_notional) if position_notional is not None else None,
            "position_risk_pct": position_risk_pct,
            "projected_margin_usage_pct": projected_margin_usage_pct,
            "account_drawdown_pct": metrics.get("account_drawdown_pct"),
            "daily_drawdown_pct": metrics.get("daily_drawdown_pct"),
            "weekly_drawdown_pct": metrics.get("weekly_drawdown_pct"),
            "daily_loss_usdt": _decimal_json(metrics.get("daily_loss_usdt", Decimal("0"))),
            "allowed_leverage": signal_payload.get("allowed_leverage"),
            "recommended_leverage": signal_payload.get("recommended_leverage"),
            "projected_rr": None,
            "portfolio_exposure": portfolio_detail,
        },
        "context": {},
    }


def _inference_timeout_rejected_risk_shape(
    *,
    limits: Any,
    signal_payload: dict[str, Any],
    metrics: dict[str, Any],
    portfolio_detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "policy_version": RISK_ENGINE_POLICY_VERSION,
        "trade_action": "do_not_trade",
        "decision_state": "rejected",
        "decision_reason": INFERENCE_TIMEOUT,
        "reasons_json": [INFERENCE_TIMEOUT],
        "signal_reasons_json": [INFERENCE_TIMEOUT],
        "market_reasons_json": [INFERENCE_TIMEOUT],
        "account_reasons_json": [],
        "position_reasons_json": [],
        "limits": asdict(limits) if limits is not None else {},
        "metrics": {
            "open_positions_count": metrics.get("open_positions_count"),
            "position_notional_usdt": None,
            "position_risk_pct": None,
            "projected_margin_usage_pct": metrics.get("current_margin_usage_pct"),
            "account_drawdown_pct": metrics.get("account_drawdown_pct"),
            "daily_drawdown_pct": metrics.get("daily_drawdown_pct"),
            "weekly_drawdown_pct": metrics.get("weekly_drawdown_pct"),
            "daily_loss_usdt": _decimal_json(metrics.get("daily_loss_usdt", Decimal("0"))),
            "allowed_leverage": signal_payload.get("allowed_leverage"),
            "recommended_leverage": signal_payload.get("recommended_leverage"),
            "projected_rr": None,
            "portfolio_exposure": portfolio_detail,
        },
        "context": {"inference_fail_closed": True},
    }


def _vpin_toxic_halt_risk_shape(
    *,
    limits: Any,
    signal_payload: dict[str, Any],
    metrics: dict[str, Any],
    portfolio_detail: dict[str, Any],
    vpin_0_1: float,
) -> dict[str, Any]:
    return {
        "policy_version": RISK_ENGINE_POLICY_VERSION,
        "trade_action": "do_not_trade",
        "decision_state": "rejected",
        "decision_reason": RISK_VPIN_HALT,
        "reasons_json": [RISK_VPIN_HALT],
        "signal_reasons_json": [],
        "market_reasons_json": [RISK_VPIN_HALT],
        "account_reasons_json": [],
        "position_reasons_json": [],
        "limits": asdict(limits) if limits is not None else {},
        "metrics": {
            "open_positions_count": metrics.get("open_positions_count"),
            "position_notional_usdt": None,
            "position_risk_pct": None,
            "projected_margin_usage_pct": metrics.get("current_margin_usage_pct"),
            "account_drawdown_pct": metrics.get("account_drawdown_pct"),
            "daily_drawdown_pct": metrics.get("daily_drawdown_pct"),
            "weekly_drawdown_pct": metrics.get("weekly_drawdown_pct"),
            "daily_loss_usdt": _decimal_json(metrics.get("daily_loss_usdt", Decimal("0"))),
            "allowed_leverage": signal_payload.get("allowed_leverage"),
            "recommended_leverage": signal_payload.get("recommended_leverage"),
            "projected_rr": None,
            "portfolio_exposure": portfolio_detail,
            "market_vpin_score_0_1": vpin_0_1,
        },
        "context": {
            "vpin_toxic_flow_guard": True,
            "market_vpin_score_0_1": vpin_0_1,
            "vpin_halt_threshold_0_1": VPIN_HARD_HALT_THRESHOLD_0_1,
        },
    }


def build_live_trade_risk_decision(
    *,
    settings: LiveBrokerSettings,
    repo: LiveBrokerRepository,
    intent: ExecutionIntentRequest,
    signal_payload: dict[str, Any],
    now_ms: int,
    survival_mode_active: bool = False,
    market_vpin_score_0_1: float | None = None,
) -> dict[str, Any]:
    metrics = build_live_account_risk_metrics(
        settings=settings,
        repo=repo,
        now_ms=now_ms,
    )

    limits = build_trade_risk_limits(settings)
    if survival_mode_active:
        limits = replace(limits, min_allowed_leverage=1)

    vpin: float | None = None
    if market_vpin_score_0_1 is not None:
        try:
            v0 = float(market_vpin_score_0_1)
        except (TypeError, ValueError):
            v0 = float("nan")
        if v0 == v0:  # not NaN
            vpin = v0

    if vpin is not None and vpin > VPIN_HARD_HALT_THRESHOLD_0_1:
        ok_pf, portfolio_detail = assert_portfolio_exposure_limit(
            settings=settings,
            repo=repo,
            intent=intent,
            total_equity=metrics["total_equity"],
        )
        _ = ok_pf
        out = _vpin_toxic_halt_risk_shape(
            limits=limits,
            signal_payload=signal_payload,
            metrics=metrics,
            portfolio_detail=portfolio_detail,
            vpin_0_1=vpin,
        )
        out["account_metrics"] = {
            "total_equity": _decimal_json(metrics["total_equity"]),
            "used_margin": _decimal_json(metrics["used_margin"]),
            "current_margin_usage_pct": metrics["current_margin_usage_pct"],
            "open_positions_count": metrics["open_positions_count"],
            "account_drawdown_pct": metrics["account_drawdown_pct"],
            "daily_drawdown_pct": metrics["daily_drawdown_pct"],
            "weekly_drawdown_pct": metrics["weekly_drawdown_pct"],
            "daily_loss_usdt": _decimal_json(metrics["daily_loss_usdt"]),
            "portfolio_exposure": portfolio_detail,
            "market_vpin_score_0_1": vpin,
        }
        return out

    if live_broker_payload_inference_blocks_trading(signal_payload):
        ok_pf, portfolio_detail = assert_portfolio_exposure_limit(
            settings=settings,
            repo=repo,
            intent=intent,
            total_equity=metrics["total_equity"],
        )
        _ = ok_pf
        out = _inference_timeout_rejected_risk_shape(
            limits=limits,
            signal_payload=signal_payload,
            metrics=metrics,
            portfolio_detail=portfolio_detail,
        )
        out["account_metrics"] = {
            "total_equity": _decimal_json(metrics["total_equity"]),
            "used_margin": _decimal_json(metrics["used_margin"]),
            "current_margin_usage_pct": metrics["current_margin_usage_pct"],
            "open_positions_count": metrics["open_positions_count"],
            "account_drawdown_pct": metrics["account_drawdown_pct"],
            "daily_drawdown_pct": metrics["daily_drawdown_pct"],
            "weekly_drawdown_pct": metrics["weekly_drawdown_pct"],
            "daily_loss_usdt": _decimal_json(metrics["daily_loss_usdt"]),
            "portfolio_exposure": portfolio_detail,
        }
        return out

    position_notional = None
    projected_margin_usage_pct = metrics["current_margin_usage_pct"]
    position_risk_pct = None
    qty = _dec(intent.qty_base)
    entry_price = _dec(intent.entry_price)
    stop_loss = _dec(intent.stop_loss)
    if qty > 0 and entry_price > 0:
        position_notional = qty * entry_price
    if position_notional is not None and position_notional > 0 and intent.leverage:
        projected_margin = position_notional / Decimal(str(intent.leverage))
        total_equity = metrics["total_equity"]
        if total_equity > 0:
            projected_margin_usage_pct = compute_margin_usage_pct(
                total_equity=total_equity,
                used_margin=metrics["used_margin"] + projected_margin,
            )
    if qty > 0 and entry_price > 0 and stop_loss > 0 and metrics["total_equity"] > 0:
        position_risk_pct = compute_position_risk_pct(
            entry_price=entry_price,
            stop_price=stop_loss,
            qty_base=qty,
            account_equity=metrics["total_equity"],
        )

    ok_portfolio, portfolio_detail = assert_portfolio_exposure_limit(
        settings=settings,
        repo=repo,
        intent=intent,
        total_equity=metrics["total_equity"],
    )
    if not ok_portfolio:
        out = _portfolio_rejected_risk_shape(
            limits=limits,
            signal_payload=signal_payload,
            metrics=metrics,
            portfolio_detail=portfolio_detail,
            position_notional=position_notional,
            projected_margin_usage_pct=projected_margin_usage_pct,
            position_risk_pct=position_risk_pct,
        )
        out["account_metrics"] = {
            "total_equity": _decimal_json(metrics["total_equity"]),
            "used_margin": _decimal_json(metrics["used_margin"]),
            "current_margin_usage_pct": metrics["current_margin_usage_pct"],
            "open_positions_count": metrics["open_positions_count"],
            "account_drawdown_pct": metrics["account_drawdown_pct"],
            "daily_drawdown_pct": metrics["daily_drawdown_pct"],
            "weekly_drawdown_pct": metrics["weekly_drawdown_pct"],
            "daily_loss_usdt": _decimal_json(metrics["daily_loss_usdt"]),
            "portfolio_exposure": portfolio_detail,
        }
        return out

    decision = evaluate_trade_risk(
        signal=signal_payload,
        limits=limits,
        open_positions_count=metrics["open_positions_count"],
        position_notional_usdt=position_notional,
        position_risk_pct=position_risk_pct,
        projected_margin_usage_pct=projected_margin_usage_pct,
        account_drawdown_pct=metrics["account_drawdown_pct"],
        daily_drawdown_pct=metrics["daily_drawdown_pct"],
        weekly_drawdown_pct=metrics["weekly_drawdown_pct"],
        daily_loss_usdt=metrics["daily_loss_usdt"],
        signal_allowed_leverage=signal_payload.get("allowed_leverage"),
        signal_recommended_leverage=signal_payload.get("recommended_leverage"),
        leverage_cap_reasons_json=signal_payload.get("leverage_cap_reasons_json") or [],
        operational_staleness_reasons=metrics["operational_staleness_reasons"],
    )
    decision["account_metrics"] = {
        "total_equity": _decimal_json(metrics["total_equity"]),
        "used_margin": _decimal_json(metrics["used_margin"]),
        "current_margin_usage_pct": metrics["current_margin_usage_pct"],
        "open_positions_count": metrics["open_positions_count"],
        "account_drawdown_pct": metrics["account_drawdown_pct"],
        "daily_drawdown_pct": metrics["daily_drawdown_pct"],
        "weekly_drawdown_pct": metrics["weekly_drawdown_pct"],
        "daily_loss_usdt": _decimal_json(metrics["daily_loss_usdt"]),
        "portfolio_exposure": portfolio_detail,
    }
    if vpin is not None:
        acctm = decision["account_metrics"]
        if isinstance(acctm, dict):
            acctm["market_vpin_score_0_1"] = vpin
            vpin_reduce = (
                vpin > VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1
                and vpin <= VPIN_HARD_HALT_THRESHOLD_0_1
            )
            if vpin_reduce:
                acctm["vpin_order_size_scale"] = 0.5
    return decision


def build_live_account_risk_metrics(
    *,
    settings: LiveBrokerSettings,
    repo: LiveBrokerRepository,
    now_ms: int,
) -> dict[str, Any]:
    account_snapshots = repo.list_latest_exchange_snapshots("account", limit=20)
    position_snapshots = repo.list_latest_exchange_snapshots("positions", limit=200)
    account_items = _flatten_snapshot_items(account_snapshots)
    position_items = _flatten_snapshot_items(position_snapshots)

    account_equity = _first_matching_decimal(
        account_items,
        margin_coin=settings.effective_margin_coin,
        fields=_ACCOUNT_EQUITY_FIELDS,
    )
    available_equity = _first_matching_decimal(
        account_items,
        margin_coin=settings.effective_margin_coin,
        fields=_ACCOUNT_AVAILABLE_FIELDS,
    )

    used_margin = _sum_position_margin(position_items)
    if account_equity > 0 and available_equity > 0 and available_equity <= account_equity:
        inferred_margin = account_equity - available_equity
        used_margin = max(used_margin, inferred_margin)

    current_margin_usage_pct = compute_margin_usage_pct(
        total_equity=account_equity,
        used_margin=used_margin,
    )

    account_history = _load_account_history(
        repo=repo,
        now_ms=now_ms,
        window_ms=None,
    )
    day_history = _load_account_history(
        repo=repo,
        now_ms=now_ms,
        window_ms=_DAY_MS,
    )
    week_history = _load_account_history(
        repo=repo,
        now_ms=now_ms,
        window_ms=_WEEK_MS,
    )
    all_drawdown = compute_drawdown_from_points(
        current_equity=account_equity,
        equity_points=account_history,
    )
    daily_drawdown = compute_drawdown_from_points(
        current_equity=account_equity,
        equity_points=day_history,
    )
    weekly_drawdown = compute_drawdown_from_points(
        current_equity=account_equity,
        equity_points=week_history,
    )

    return {
        "total_equity": account_equity,
        "used_margin": used_margin,
        "current_margin_usage_pct": current_margin_usage_pct,
        "open_positions_count": _open_positions_count(position_items),
        "account_drawdown_pct": all_drawdown["drawdown_pct"],
        "daily_drawdown_pct": daily_drawdown["drawdown_pct"],
        "weekly_drawdown_pct": weekly_drawdown["drawdown_pct"],
        "daily_loss_usdt": _dec(daily_drawdown["loss_usdt"]),
        "operational_staleness_reasons": _operational_staleness_reasons(repo),
    }


def _load_account_history(
    *,
    repo: LiveBrokerRepository,
    now_ms: int,
    window_ms: int | None,
) -> list[str]:
    if hasattr(repo, "list_exchange_snapshots_since"):
        if window_ms is None:
            since_ts_ms = 0
        else:
            since_ts_ms = max(0, now_ms - window_ms)
        snapshots = repo.list_exchange_snapshots_since(  # type: ignore[attr-defined]
            "account",
            since_ts_ms=since_ts_ms,
            limit=5000,
        )
    else:
        snapshots = repo.list_latest_exchange_snapshots("account", limit=200)
    items = _flatten_snapshot_items(snapshots)
    out: list[str] = []
    for item in items:
        value = _first_decimal(item, _ACCOUNT_EQUITY_FIELDS) or _first_decimal(
            item, _ACCOUNT_AVAILABLE_FIELDS
        )
        if value > 0:
            out.append(format(value, "f"))
    return out


def _operational_staleness_reasons(repo: LiveBrokerRepository) -> list[str]:
    if not hasattr(repo, "latest_reconcile_snapshot"):
        return []
    latest = repo.latest_reconcile_snapshot()  # type: ignore[attr-defined]
    if not isinstance(latest, dict):
        return []
    details = latest.get("details_json") or {}
    if not isinstance(details, dict):
        return []
    drift = details.get("drift") or {}
    if not isinstance(drift, dict):
        return []
    snapshot_health = drift.get("snapshot_health") or {}
    if not isinstance(snapshot_health, dict):
        return []
    reasons: list[str] = []
    for item in snapshot_health.get("missing_types") or []:
        if isinstance(item, str) and item.strip():
            reasons.append(f"live_snapshot_{item.strip().lower()}_missing")
    for item in snapshot_health.get("stale_types") or []:
        if isinstance(item, str) and item.strip():
            reasons.append(f"live_snapshot_{item.strip().lower()}_stale")
    return reasons


def _open_positions_count(items: list[dict[str, Any]]) -> int:
    total = 0
    for item in items:
        size = _first_decimal(item, _POSITION_SIZE_FIELDS)
        if size > 0:
            total += 1
    return total


def _sum_position_margin(items: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for item in items:
        total += _first_decimal(item, _POSITION_MARGIN_FIELDS)
    return total


def _flatten_snapshot_items(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for snapshot in snapshots:
        raw = snapshot.get("raw_data") or {}
        if not isinstance(raw, dict):
            continue
        items = raw.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                out.append(dict(item))
    return out


def _first_matching_decimal(
    items: list[dict[str, Any]],
    *,
    margin_coin: str,
    fields: tuple[str, ...],
) -> Decimal:
    for item in items:
        item_margin_coin = str(item.get("marginCoin") or item.get("coin") or "").strip().upper()
        if item_margin_coin and item_margin_coin != str(margin_coin).strip().upper():
            continue
        value = _first_decimal(item, fields)
        if value > 0:
            return value
    for item in items:
        value = _first_decimal(item, fields)
        if value > 0:
            return value
    return Decimal("0")


def _first_decimal(item: dict[str, Any], fields: tuple[str, ...]) -> Decimal:
    for field in fields:
        value = _dec(item.get(field))
        if value > 0:
            return value
    return Decimal("0")


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _decimal_json(value: Decimal) -> str:
    return format(value, "f")
