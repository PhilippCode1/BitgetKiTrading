#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_py.market_data_quality import (
    build_asset_data_quality_summary,
    detect_candle_gaps,
    summary_to_dict,
    validate_candle_sequence,
    validate_funding_freshness,
    validate_ohlc_sanity,
    validate_orderbook_freshness,
    validate_spread_sanity,
)

def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _load_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "symbol": "ETHUSDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "data_source": "dry_run_fixture",
            "candles": [
                {"ts_ms": 1_700_000_000_000, "open": 3000, "high": 3010, "low": 2990, "close": 3005, "volume": 1234},
                {"ts_ms": 1_700_000_060_000, "open": 3005, "high": 3020, "low": 3000, "close": 3015, "volume": 1400},
            ],
            "expected_candle_interval_ms": 60_000,
            "orderbook_present": True,
            "last_orderbook_ts_ms": 1_700_000_060_000,
            "now_ts_ms": 1_700_000_070_000,
            "orderbook_max_age_ms": 30_000,
            "best_bid": 3014.8,
            "best_ask": 3015.2,
            "max_spread_bps": 20.0,
            "funding_last_ts_ms": 1_700_000_050_000,
            "funding_max_age_ms": 3_600_000,
            "funding_required_for_strategy": False,
            "delisted": False,
            "suspended": False,
            "provider_error_rate": 0.0,
            "provider_error_rate_max": 0.05,
            "signal_input_complete": True,
            "instrument_metadata_fresh": True,
            "market_family_clear": True,
            "product_type_clear": True,
            "redis_fresh": True,
            "oi_fresh": True,
            "oi_required": False,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    candles = list(payload.get("candles") or [])

    ok_seq, seq_reasons = validate_candle_sequence(candles)
    if not ok_seq:
        reasons.extend(seq_reasons)
    ok_gaps, gap_reasons = detect_candle_gaps(candles, int(payload.get("expected_candle_interval_ms", 0)))
    if not ok_gaps:
        reasons.extend(gap_reasons)
    ok_ohlc, ohlc_reasons = validate_ohlc_sanity(candles)
    if not ok_ohlc:
        reasons.extend(ohlc_reasons)

    ok_ob, ob_reasons = validate_orderbook_freshness(
        orderbook_present=bool(payload.get("orderbook_present")),
        last_orderbook_ts_ms=payload.get("last_orderbook_ts_ms"),
        now_ts_ms=int(payload.get("now_ts_ms", 0)),
        max_age_ms=int(payload.get("orderbook_max_age_ms", 0)),
    )
    if not ok_ob:
        reasons.extend(ob_reasons)

    ok_spread, spread_reasons, spread_warnings = validate_spread_sanity(
        bid=(float(payload["best_bid"]) if payload.get("best_bid") is not None else None),
        ask=(float(payload["best_ask"]) if payload.get("best_ask") is not None else None),
        max_spread_bps=float(payload.get("max_spread_bps", 0)),
    )
    if not ok_spread:
        reasons.extend(spread_reasons)
    warnings.extend(spread_warnings)

    ok_funding, funding_reasons, funding_warnings = validate_funding_freshness(
        market_family=str(payload.get("market_family") or ""),
        funding_last_ts_ms=payload.get("funding_last_ts_ms"),
        now_ts_ms=int(payload.get("now_ts_ms", 0)),
        max_age_ms=int(payload.get("funding_max_age_ms", 0)),
        funding_required_for_strategy=bool(payload.get("funding_required_for_strategy")),
    )
    if not ok_funding:
        reasons.extend(funding_reasons)
    warnings.extend(funding_warnings)

    if bool(payload.get("delisted")):
        reasons.append("asset_delisted")
    if bool(payload.get("suspended")):
        reasons.append("asset_suspended")
    if float(payload.get("provider_error_rate", 0.0)) > float(payload.get("provider_error_rate_max", 1.0)):
        reasons.append("provider_error_rate_too_high")
    if not bool(payload.get("redis_fresh", True)):
        reasons.append("redis_eventbus_stale")
    if not bool(payload.get("signal_input_complete", True)):
        reasons.append("signal_input_incomplete")
    if not bool(payload.get("instrument_metadata_fresh", True)):
        reasons.append("instrument_metadata_stale")
    if not bool(payload.get("market_family_clear", True)):
        reasons.append("market_family_ambiguous")
    if not bool(payload.get("product_type_clear", True)):
        reasons.append("product_type_ambiguous")
    if bool(payload.get("oi_required")) and not bool(payload.get("oi_fresh", False)):
        warnings.append("open_interest_stale_warning")

    deduped_reasons = list(dict.fromkeys(reasons))
    deduped_warnings = list(dict.fromkeys(warnings))
    if deduped_reasons:
        quality_status = "data_live_blocked"
    elif deduped_warnings:
        quality_status = "data_warning"
    else:
        quality_status = "data_ok"

    summary = build_asset_data_quality_summary(
        symbol=str(payload.get("symbol") or ""),
        market_family=str(payload.get("market_family") or ""),
        product_type=payload.get("product_type"),
        data_source=str(payload.get("data_source") or "unknown"),
        quality_status=quality_status,
        block_reasons=deduped_reasons,
        warnings=deduped_warnings,
    )
    out = summary_to_dict(summary)
    out["git_sha"] = _git_sha()
    return out


def render_markdown(summary: dict[str, Any]) -> str:
    def _fmt_list(values: list[str]) -> str:
        if not values:
            return "- keine"
        return "\n".join(f"- {item}" for item in values)

    return (
        "# Asset Data Quality Report\n\n"
        f"- Datum/Zeit: `{summary['timestamp_utc']}`\n"
        f"- Git SHA: `{summary.get('git_sha', 'unknown')}`\n"
        f"- Asset/Symbol: `{summary['symbol']}`\n"
        f"- MarketFamily: `{summary['market_family']}`\n"
        f"- ProductType: `{summary.get('product_type')}`\n"
        f"- Datenquelle: `{summary['data_source']}`\n"
        f"- Quality Status: `{summary['quality_status']}`\n"
        f"- Live-Auswirkung: `{summary['live_impact']}`\n"
        f"- Ergebnis: `{summary['result']}`\n\n"
        "## Block Reasons\n"
        f"{_fmt_list(summary.get('block_reasons', []))}\n\n"
        "## Warnings\n"
        f"{_fmt_list(summary.get('warnings', []))}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate per-asset data quality report.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)

    payload = _load_payload(args.input_json if not args.dry_run else None)
    summary = evaluate_payload(payload)
    markdown = render_markdown(summary)

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown, encoding="utf-8")
        print(f"wrote report: {args.output_md}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
