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
    evaluate_market_data_quality,
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
            "last_price": 3015.0,
            "mark_price": 3014.9,
            "index_price": 3015.1,
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
            "runtime_data": False,
            "exchange_truth_checked": False,
            "alert_route_verified": False,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = evaluate_market_data_quality(payload)
    summary = {
        "asset": result.asset,
        "market_family": result.market_family,
        "status": result.status,
        "live_allowed": result.live_allowed,
        "paper_allowed": result.paper_allowed,
        "shadow_allowed": result.shadow_allowed,
        "reasons": result.reasons,
        "freshness": result.freshness,
        "gaps": result.gaps,
        "plausibility": result.plausibility,
        "cross_source": result.cross_source,
        "checked_at": result.checked_at,
        "evidence_level": result.evidence_level,
        "alert_required": result.alert_required,
        "alert_route_verified": result.alert_route_verified,
        "data_source": str(payload.get("data_source") or "unknown"),
        "git_sha": _git_sha(),
    }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    def _fmt_list(values: list[str]) -> str:
        if not values:
            return "- keine"
        return "\n".join(f"- {item}" for item in values)

    return (
        "# Asset Data Quality Report\n\n"
        f"- Datum/Zeit: `{summary['checked_at']}`\n"
        f"- Git SHA: `{summary.get('git_sha', 'unknown')}`\n"
        f"- Asset/Symbol: `{summary['asset']}`\n"
        f"- MarketFamily: `{summary['market_family']}`\n"
        f"- Status: `{summary['status']}`\n"
        f"- Evidence-Level: `{summary['evidence_level']}`\n"
        f"- Datenquelle: `{summary['data_source']}`\n"
        f"- Live erlaubt: `{summary['live_allowed']}`\n"
        f"- Shadow erlaubt: `{summary['shadow_allowed']}`\n"
        f"- Paper erlaubt: `{summary['paper_allowed']}`\n"
        f"- Alert erforderlich: `{summary['alert_required']}`\n"
        f"- Alert-Route verifiziert: `{summary['alert_route_verified']}`\n\n"
        "## Block Reasons\n"
        f"{_fmt_list(summary.get('reasons', []))}\n\n"
        "## Freshness\n"
        f"- price_tick_age_ms: `{summary['freshness'].get('price_tick_age_ms')}`\n"
        f"- orderbook_age_ms: `{summary['freshness'].get('orderbook_age_ms')}`\n"
        f"- funding_age_ms: `{summary['freshness'].get('funding_age_ms')}`\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate per-asset data quality report.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
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
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote report: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
