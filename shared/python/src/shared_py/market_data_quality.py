from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

DataQualityStatus = Literal[
    "data_unknown",
    "data_ok",
    "data_warning",
    "data_stale",
    "data_incomplete",
    "data_invalid",
    "data_provider_error",
    "data_quarantined",
    "data_live_blocked",
]
EvidenceLevel = Literal["synthetic", "runtime", "external_required"]

PASS_OUTCOME = "PASS"
PASS_WITH_WARNINGS_OUTCOME = "PASS_WITH_WARNINGS"
FAIL_OUTCOME = "FAIL"
UNKNOWN_OUTCOME = "UNKNOWN"

_BLOCKING_STATUSES = {
    "data_unknown",
    "data_stale",
    "data_incomplete",
    "data_invalid",
    "data_provider_error",
    "data_quarantined",
    "data_live_blocked",
}


@dataclass(frozen=True)
class AssetDataQualitySummary:
    timestamp_utc: str
    symbol: str
    market_family: str
    product_type: str | None
    data_source: str
    quality_status: DataQualityStatus
    block_reasons: list[str]
    warnings: list[str]
    live_impact: str
    result: str


@dataclass(frozen=True)
class AssetMarketDataQualityResult:
    asset: str
    market_family: str
    status: Literal["pass", "warn", "fail", "not_enough_evidence"]
    live_allowed: bool
    paper_allowed: bool
    shadow_allowed: bool
    reasons: list[str]
    freshness: dict[str, Any]
    gaps: dict[str, Any]
    plausibility: dict[str, Any]
    cross_source: dict[str, Any]
    checked_at: str
    evidence_level: EvidenceLevel
    alert_required: bool
    alert_route_verified: bool


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_candle_sequence(candles: list[dict]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not candles:
        return False, ["candles_missing"]
    last_ts: int | None = None
    for row in candles:
        ts = int(row.get("ts_ms") or 0)
        if ts <= 0:
            reasons.append("candle_invalid_timestamp")
            continue
        if last_ts is not None and ts <= last_ts:
            reasons.append("candle_out_of_order")
        last_ts = ts
    return len(reasons) == 0, list(dict.fromkeys(reasons))


def detect_duplicate_candles(candles: list[dict]) -> tuple[bool, list[str]]:
    if not candles:
        return False, ["candles_missing"]
    seen: set[int] = set()
    duplicates = 0
    for row in candles:
        ts = int(row.get("ts_ms") or 0)
        if ts <= 0:
            continue
        if ts in seen:
            duplicates += 1
        seen.add(ts)
    if duplicates == 0:
        return True, []
    if duplicates >= 2:
        return False, ["candle_duplicates_critical"]
    return True, ["candle_duplicates_warning"]


def detect_out_of_order_candles(candles: list[dict]) -> tuple[bool, list[str]]:
    if not candles:
        return False, ["candles_missing"]
    reasons: list[str] = []
    last_ts: int | None = None
    for row in candles:
        ts = int(row.get("ts_ms") or 0)
        if ts <= 0:
            continue
        if last_ts is not None and ts < last_ts:
            reasons.append("candle_out_of_order")
        last_ts = ts
    return len(reasons) == 0, list(dict.fromkeys(reasons))


def detect_candle_gaps(candles: list[dict], expected_interval_ms: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not candles:
        return False, ["candles_missing"]
    if expected_interval_ms <= 0:
        return False, ["expected_interval_invalid"]
    ordered = sorted(int(c.get("ts_ms") or 0) for c in candles if int(c.get("ts_ms") or 0) > 0)
    if len(ordered) < 2:
        return True, []
    for idx in range(1, len(ordered)):
        delta = ordered[idx] - ordered[idx - 1]
        if delta > expected_interval_ms * 2:
            reasons.append("candle_critical_gap")
            break
    return len(reasons) == 0, reasons


def validate_ohlc_sanity(candles: list[dict]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for row in candles:
        try:
            open_ = float(row.get("open"))
            high = float(row.get("high"))
            low = float(row.get("low"))
            close = float(row.get("close"))
            vol = float(row.get("volume", 0.0))
        except (TypeError, ValueError):
            reasons.append("ohlc_not_numeric")
            continue
        if min(open_, high, low, close) <= 0:
            reasons.append("ohlc_non_positive")
        if high < low:
            reasons.append("ohlc_high_below_low")
        if open_ > high or open_ < low or close > high or close < low:
            reasons.append("ohlc_range_violation")
        if vol < 0:
            reasons.append("volume_negative")
    return len(reasons) == 0, list(dict.fromkeys(reasons))


def validate_orderbook_freshness(
    *,
    orderbook_present: bool,
    last_orderbook_ts_ms: int | None,
    now_ts_ms: int,
    max_age_ms: int,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not orderbook_present:
        reasons.append("orderbook_missing")
        return False, reasons
    if not last_orderbook_ts_ms or last_orderbook_ts_ms <= 0:
        reasons.append("orderbook_timestamp_missing")
        return False, reasons
    if max_age_ms <= 0:
        reasons.append("orderbook_max_age_invalid")
        return False, reasons
    if now_ts_ms - int(last_orderbook_ts_ms) > max_age_ms:
        reasons.append("orderbook_stale")
    return len(reasons) == 0, reasons


def validate_spread_sanity(
    *,
    bid: float | None,
    ask: float | None,
    max_spread_bps: float,
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    if bid is None or ask is None:
        return False, ["top_of_book_missing"], warnings
    if bid <= 0 or ask <= 0:
        return False, ["top_of_book_non_positive"], warnings
    if ask < bid:
        return False, ["top_of_book_crossed"], warnings
    mid = (bid + ask) / 2.0
    spread_bps = ((ask - bid) / mid) * 10000.0 if mid > 0 else 0.0
    if spread_bps > max_spread_bps:
        reasons.append("spread_extreme")
    elif spread_bps > max_spread_bps * 0.8:
        warnings.append("spread_elevated")
    return len(reasons) == 0, reasons, warnings


def validate_price_plausibility(
    *,
    bid: float | None,
    ask: float | None,
    last_price: float | None,
    mark_price: float | None,
    index_price: float | None,
    max_mark_index_deviation_bps: float = 80.0,
    max_last_mid_deviation_bps: float = 120.0,
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    for name, value in (
        ("bid", bid),
        ("ask", ask),
        ("last_price", last_price),
        ("mark_price", mark_price),
        ("index_price", index_price),
    ):
        if value is not None and value <= 0:
            reasons.append(f"{name}_non_positive")
    if bid is not None and ask is not None and bid > ask:
        reasons.append("bid_gt_ask")
    if bid is not None and ask is not None and last_price is not None and bid <= ask:
        mid = (bid + ask) / 2.0
        if mid > 0:
            dev_bps = abs(last_price - mid) / mid * 10_000.0
            if dev_bps > max_last_mid_deviation_bps:
                reasons.append("last_price_implausible_vs_mid")
    if mark_price is not None and index_price is not None and index_price > 0:
        dev_bps = abs(mark_price - index_price) / index_price * 10_000.0
        if dev_bps > max_mark_index_deviation_bps:
            reasons.append("mark_index_deviation_too_high")
        elif dev_bps > max_mark_index_deviation_bps * 0.7:
            warnings.append("mark_index_deviation_elevated")
    return len(reasons) == 0, list(dict.fromkeys(reasons)), list(dict.fromkeys(warnings))


def validate_timestamp_guard(
    *,
    tick_ts_ms: int | None,
    now_ts_ms: int,
    max_future_tolerance_ms: int = 3_000,
) -> tuple[bool, list[str]]:
    if not tick_ts_ms or tick_ts_ms <= 0:
        return False, ["tick_timestamp_missing"]
    delta = int(tick_ts_ms) - int(now_ts_ms)
    if delta > max_future_tolerance_ms:
        return False, ["tick_timestamp_from_future"]
    return True, []


def validate_funding_freshness(
    *,
    market_family: str,
    funding_last_ts_ms: int | None,
    now_ts_ms: int,
    max_age_ms: int,
    funding_required_for_strategy: bool,
) -> tuple[bool, list[str], list[str]]:
    if market_family != "futures":
        return True, [], []
    if not funding_last_ts_ms or funding_last_ts_ms <= 0:
        if funding_required_for_strategy:
            return False, ["funding_missing"], []
        return True, [], ["funding_missing_warning"]
    if now_ts_ms - int(funding_last_ts_ms) > max_age_ms:
        if funding_required_for_strategy:
            return False, ["funding_stale"], []
        return True, [], ["funding_stale_warning"]
    return True, [], []


def validate_open_interest_freshness(
    *,
    market_family: str,
    oi_last_ts_ms: int | None,
    now_ts_ms: int,
    max_age_ms: int,
    oi_required_for_strategy: bool,
) -> tuple[bool, list[str], list[str]]:
    if market_family != "futures":
        return True, [], []
    if not oi_last_ts_ms or oi_last_ts_ms <= 0:
        if oi_required_for_strategy:
            return False, ["open_interest_missing"], []
        return True, [], ["open_interest_missing_warning"]
    if now_ts_ms - int(oi_last_ts_ms) > max_age_ms:
        if oi_required_for_strategy:
            return False, ["open_interest_stale"], []
        return True, [], ["open_interest_stale_warning"]
    return True, [], []


def asset_data_quality_blocks_live(
    *,
    quality_status: DataQualityStatus,
    block_reasons: list[str],
) -> bool:
    if quality_status in _BLOCKING_STATUSES:
        return True
    return any(bool(str(reason).strip()) for reason in block_reasons)


def evaluate_market_data_quality(payload: dict[str, Any]) -> AssetMarketDataQualityResult:
    now_ts_ms = int(payload.get("now_ts_ms") or 0)
    market_family = str(payload.get("market_family") or "unknown").lower()
    is_runtime = bool(payload.get("runtime_data", False))
    exchange_truth_checked = bool(payload.get("exchange_truth_checked", False))
    alert_route_verified = bool(payload.get("alert_route_verified", False))

    ok_ob, ob_reasons = validate_orderbook_freshness(
        orderbook_present=bool(payload.get("orderbook_present")),
        last_orderbook_ts_ms=payload.get("last_orderbook_ts_ms"),
        now_ts_ms=now_ts_ms,
        max_age_ms=int(payload.get("orderbook_max_age_ms") or 0),
    )
    ok_cseq, cseq_reasons = validate_candle_sequence(list(payload.get("candles") or []))
    ok_gap, gap_reasons = detect_candle_gaps(
        list(payload.get("candles") or []),
        int(payload.get("expected_candle_interval_ms") or 0),
    )
    ok_ohlc, ohlc_reasons = validate_ohlc_sanity(list(payload.get("candles") or []))
    ok_spread, spread_reasons, spread_warnings = validate_spread_sanity(
        bid=(float(payload["best_bid"]) if payload.get("best_bid") is not None else None),
        ask=(float(payload["best_ask"]) if payload.get("best_ask") is not None else None),
        max_spread_bps=float(payload.get("max_spread_bps") or 50.0),
    )
    ok_ts, ts_reasons = validate_timestamp_guard(
        tick_ts_ms=payload.get("price_tick_ts_ms") or payload.get("last_orderbook_ts_ms"),
        now_ts_ms=now_ts_ms,
        max_future_tolerance_ms=int(payload.get("max_future_tolerance_ms") or 3_000),
    )
    ok_pl, pl_reasons, pl_warnings = validate_price_plausibility(
        bid=(float(payload["best_bid"]) if payload.get("best_bid") is not None else None),
        ask=(float(payload["best_ask"]) if payload.get("best_ask") is not None else None),
        last_price=(float(payload["last_price"]) if payload.get("last_price") is not None else None),
        mark_price=(float(payload["mark_price"]) if payload.get("mark_price") is not None else None),
        index_price=(float(payload["index_price"]) if payload.get("index_price") is not None else None),
        max_mark_index_deviation_bps=float(payload.get("max_mark_index_deviation_bps") or 80.0),
        max_last_mid_deviation_bps=float(payload.get("max_last_mid_deviation_bps") or 120.0),
    )

    reasons: list[str] = []
    warnings: list[str] = []
    if not ok_ob:
        reasons.extend(ob_reasons)
    if not ok_cseq:
        reasons.extend(cseq_reasons)
    if not ok_gap:
        reasons.extend(gap_reasons)
    if not ok_ohlc:
        reasons.extend(ohlc_reasons)
    if not ok_spread:
        reasons.extend(spread_reasons)
    if not ok_ts:
        reasons.extend(ts_reasons)
    if not ok_pl:
        reasons.extend(pl_reasons)
    warnings.extend(spread_warnings)
    warnings.extend(pl_warnings)

    if bool(payload.get("provider_unavailable")) or bool(payload.get("redis_unavailable")):
        reasons.append("provider_or_cache_unavailable")
    if market_family == "futures":
        if payload.get("mark_price") is None:
            reasons.append("mark_price_missing_for_futures")
        if payload.get("product_type") in (None, ""):
            reasons.append("product_type_missing_for_futures")
    if market_family == "margin" and payload.get("margin_coin") in (None, ""):
        reasons.append("margin_coin_missing_for_margin")
    if not exchange_truth_checked:
        warnings.append("exchange_truth_not_checked")

    reasons = list(dict.fromkeys(reasons))
    warnings = list(dict.fromkeys(warnings))
    evidence_level: EvidenceLevel = "runtime" if is_runtime else "synthetic"
    if not exchange_truth_checked:
        evidence_level = "external_required"
    if reasons:
        status: Literal["pass", "warn", "fail", "not_enough_evidence"] = "fail"
    elif warnings:
        status = "not_enough_evidence" if "exchange_truth_not_checked" in warnings else "warn"
    else:
        status = "pass"

    live_allowed = status == "pass" and evidence_level == "runtime" and exchange_truth_checked
    return AssetMarketDataQualityResult(
        asset=str(payload.get("symbol") or "").upper(),
        market_family=market_family,
        status=status,
        live_allowed=live_allowed,
        paper_allowed=True,
        shadow_allowed=True,
        reasons=reasons + ([] if live_allowed else (["quality_not_live_eligible"] if status != "pass" else ["runtime_evidence_missing"])),
        freshness={
            "price_tick_age_ms": int(payload.get("price_tick_age_ms") or 0),
            "orderbook_age_ms": int(payload.get("now_ts_ms") or 0) - int(payload.get("last_orderbook_ts_ms") or 0),
            "funding_age_ms": None if payload.get("funding_last_ts_ms") is None else int(payload.get("now_ts_ms") or 0) - int(payload.get("funding_last_ts_ms") or 0),
        },
        gaps={"candle_gap_detected": "candle_critical_gap" in reasons},
        plausibility={"warnings": warnings, "checks_passed": len(pl_reasons) == 0 and len(spread_reasons) == 0},
        cross_source={
            "exchange_truth_checked": exchange_truth_checked,
            "provider_vs_exchange_consistent": "mark_index_deviation_too_high" not in reasons,
        },
        checked_at=_iso_utc_now(),
        evidence_level=evidence_level,
        alert_required=bool(reasons) or ("exchange_truth_not_checked" in warnings),
        alert_route_verified=alert_route_verified,
    )


def build_asset_data_quality_summary(
    *,
    symbol: str,
    market_family: str,
    product_type: str | None,
    data_source: str,
    quality_status: DataQualityStatus,
    block_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> AssetDataQualitySummary:
    reasons = list(dict.fromkeys(block_reasons or []))
    warns = list(dict.fromkeys(warnings or []))
    blocked = asset_data_quality_blocks_live(quality_status=quality_status, block_reasons=reasons)
    if quality_status == "data_unknown":
        result = UNKNOWN_OUTCOME
        live_impact = "LIVE_BLOCKED"
    elif blocked:
        result = FAIL_OUTCOME
        live_impact = "LIVE_BLOCKED"
    elif warns:
        result = PASS_WITH_WARNINGS_OUTCOME
        live_impact = "LIVE_ALLOWED_WITH_WARNINGS"
    else:
        result = PASS_OUTCOME
        live_impact = "LIVE_ALLOWED"
    return AssetDataQualitySummary(
        timestamp_utc=_iso_utc_now(),
        symbol=str(symbol).upper(),
        market_family=str(market_family).lower(),
        product_type=(str(product_type).upper() if product_type else None),
        data_source=data_source,
        quality_status=quality_status,
        block_reasons=reasons,
        warnings=warns,
        live_impact=live_impact,
        result=result,
    )


def summary_to_dict(summary: AssetDataQualitySummary) -> dict:
    return asdict(summary)


def build_market_data_quality_summary_de(summary: AssetDataQualitySummary) -> str:
    status_map = {
        "data_ok": "PASS",
        "data_warning": "PASS_WITH_WARNINGS",
        "data_unknown": "UNKNOWN",
        "data_stale": "FAIL",
        "data_incomplete": "FAIL",
        "data_invalid": "FAIL",
        "data_provider_error": "FAIL",
        "data_quarantined": "FAIL",
        "data_live_blocked": "FAIL",
    }
    status_de = status_map.get(summary.quality_status, "UNKNOWN")
    reasons = ", ".join(summary.block_reasons) if summary.block_reasons else "keine"
    warnings = ", ".join(summary.warnings) if summary.warnings else "keine"
    return (
        f"Asset {summary.symbol}: Datenqualitaet {status_de}, "
        f"Live-Auswirkung {summary.live_impact}, Blockgruende: {reasons}, Warnungen: {warnings}"
    )
