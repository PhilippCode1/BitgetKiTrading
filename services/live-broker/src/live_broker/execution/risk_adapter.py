from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from shared_py.risk_engine import (
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


def build_live_trade_risk_decision(
    *,
    settings: "LiveBrokerSettings",
    repo: "LiveBrokerRepository",
    intent: "ExecutionIntentRequest",
    signal_payload: dict[str, Any],
    now_ms: int,
    survival_mode_active: bool = False,
) -> dict[str, Any]:
    metrics = build_live_account_risk_metrics(
        settings=settings,
        repo=repo,
        now_ms=now_ms,
    )

    limits = build_trade_risk_limits(settings)
    if survival_mode_active:
        limits = replace(limits, min_allowed_leverage=1)

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
    }
    return decision


def build_live_account_risk_metrics(
    *,
    settings: "LiveBrokerSettings",
    repo: "LiveBrokerRepository",
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
    repo: "LiveBrokerRepository",
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


def _operational_staleness_reasons(repo: "LiveBrokerRepository") -> list[str]:
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
