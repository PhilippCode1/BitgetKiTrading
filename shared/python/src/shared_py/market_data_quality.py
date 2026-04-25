from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

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
