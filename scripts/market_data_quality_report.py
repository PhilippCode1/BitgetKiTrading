#!/usr/bin/env python3
"""Erzeugt einen Market-Data-Qualitaetsreport pro Asset (Fixture/Read-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.market_data_quality import (  # noqa: E402
    build_asset_data_quality_summary,
    build_market_data_quality_summary_de,
    detect_candle_gaps,
    detect_duplicate_candles,
    detect_out_of_order_candles,
    validate_candle_sequence,
    validate_funding_freshness,
    validate_ohlc_sanity,
    validate_open_interest_freshness,
    validate_orderbook_freshness,
    validate_spread_sanity,
)

DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "market_data_quality_sample.json"


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _redact_secret_like_values(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw in value.items():
            k = str(key).lower()
            if any(tok in k for tok in ("secret", "token", "password", "key")):
                out[key] = "***REDACTED***"
            else:
                out[key] = _redact_secret_like_values(raw)
        return out
    if isinstance(value, list):
        return [_redact_secret_like_values(item) for item in value]
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_asset(asset: dict[str, Any]) -> dict[str, Any]:
    symbol = str(asset.get("symbol") or "UNKNOWN").upper()
    market_family = str(asset.get("market_family") or "spot").lower()
    product_type = asset.get("product_type")
    data_source = str(asset.get("data_source") or "fixture")
    candles = list(asset.get("candles") or [])
    expected_interval_ms = int(asset.get("expected_interval_ms") or 60_000)
    now_ts_ms = int(asset.get("now_ts_ms") or 0)
    funding_required = bool(asset.get("funding_required_for_strategy"))
    oi_required = bool(asset.get("oi_required_for_strategy"))
    block_reasons: list[str] = []
    warnings: list[str] = []

    seq_ok, seq_reasons = validate_candle_sequence(candles)
    if not seq_ok:
        block_reasons.extend(seq_reasons)
    gap_ok, gap_reasons = detect_candle_gaps(candles, expected_interval_ms=expected_interval_ms)
    if not gap_ok:
        block_reasons.extend(gap_reasons)
    dup_ok, dup_reasons = detect_duplicate_candles(candles)
    if dup_ok and dup_reasons:
        warnings.extend(dup_reasons)
    elif not dup_ok:
        block_reasons.extend(dup_reasons)
    order_ok, order_reasons = detect_out_of_order_candles(candles)
    if not order_ok:
        block_reasons.extend(order_reasons)
    ohlc_ok, ohlc_reasons = validate_ohlc_sanity(candles)
    if not ohlc_ok:
        block_reasons.extend(ohlc_reasons)

    ob_ok, ob_reasons = validate_orderbook_freshness(
        orderbook_present=bool(asset.get("orderbook_present")),
        last_orderbook_ts_ms=asset.get("last_orderbook_ts_ms"),
        now_ts_ms=now_ts_ms,
        max_age_ms=int(asset.get("orderbook_max_age_ms") or 10_000),
    )
    if not ob_ok:
        block_reasons.extend(ob_reasons)
    spread_ok, spread_reasons, spread_warn = validate_spread_sanity(
        bid=asset.get("bid"),
        ask=asset.get("ask"),
        max_spread_bps=float(asset.get("max_spread_bps") or 60.0),
    )
    if not spread_ok:
        block_reasons.extend(spread_reasons)
    warnings.extend(spread_warn)

    funding_ok, funding_reasons, funding_warn = validate_funding_freshness(
        market_family=market_family,
        funding_last_ts_ms=asset.get("funding_last_ts_ms"),
        now_ts_ms=now_ts_ms,
        max_age_ms=int(asset.get("funding_max_age_ms") or 3_600_000),
        funding_required_for_strategy=funding_required,
    )
    if not funding_ok:
        block_reasons.extend(funding_reasons)
    warnings.extend(funding_warn)

    oi_ok, oi_reasons, oi_warn = validate_open_interest_freshness(
        market_family=market_family,
        oi_last_ts_ms=asset.get("oi_last_ts_ms"),
        now_ts_ms=now_ts_ms,
        max_age_ms=int(asset.get("oi_max_age_ms") or 3_600_000),
        oi_required_for_strategy=oi_required,
    )
    if not oi_ok:
        block_reasons.extend(oi_reasons)
    warnings.extend(oi_warn)

    explicit_status = str(asset.get("quality_status") or "").strip().lower()
    if explicit_status in {"data_ok", "data_warning", "data_stale", "data_incomplete", "data_invalid", "data_provider_error", "data_quarantined", "data_live_blocked", "data_unknown"}:
        quality_status = explicit_status
    elif block_reasons:
        quality_status = "data_live_blocked"
    elif warnings:
        quality_status = "data_warning"
    else:
        quality_status = "data_ok"

    summary = build_asset_data_quality_summary(
        symbol=symbol,
        market_family=market_family,
        product_type=product_type,
        data_source=data_source,
        quality_status=quality_status,  # type: ignore[arg-type]
        block_reasons=block_reasons,
        warnings=warnings,
    )
    return {
        "symbol": symbol,
        "summary": summary,
        "summary_de": build_market_data_quality_summary_de(summary),
    }


def _status_bucket(quality_status: str) -> str:
    if quality_status == "data_ok":
        return "PASS"
    if quality_status == "data_warning":
        return "PASS_WITH_WARNINGS"
    if quality_status == "data_unknown":
        return "UNKNOWN"
    return "FAIL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    if args.dry_run:
        print("market_data_quality_report: dry-run=true (fixture/read-only)")
        print("planned_steps=load_fixture,validate_assets,build_report")
        return 0

    input_path = args.input_json or DEFAULT_INPUT
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    assets = payload if isinstance(payload, list) else payload.get("assets", [])
    evaluated = [evaluate_asset(item) for item in assets]
    summaries = [item["summary"] for item in evaluated]
    buckets = Counter(_status_bucket(summary.quality_status) for summary in summaries)
    all_reasons: Counter[str] = Counter()
    live_blockers: list[str] = []
    for summary in summaries:
        all_reasons.update(summary.block_reasons)
        if summary.live_impact == "LIVE_BLOCKED":
            live_blockers.append(summary.symbol)

    out_payload = {
        "generated_at": _now_iso(),
        "git_sha": _git_sha(),
        "assets_checked": len(summaries),
        "status_by_asset": {
            summary.symbol: _status_bucket(summary.quality_status) for summary in summaries
        },
        "status_counts": dict(sorted(buckets.items())),
        "top_data_errors": all_reasons.most_common(10),
        "live_blockers": sorted(set(live_blockers)),
        "next_steps": [
            "Echte Bitget-Read-only-Datenqualitaetslaeufe fuer alle aktiven Assets durchführen.",
            "Fail/Unknown Assets in Main Console 'Datenqualitaet' priorisiert anzeigen.",
            "Funding/OI-Warnungen fuer strategie-relevante Assets zu Blockern hochstufen.",
        ],
        "summary_de": [item["summary_de"] for item in evaluated],
    }
    out_payload = _redact_secret_like_values(out_payload)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        lines = [
            "# Market Data Qualitaetsreport",
            "",
            f"- Datum/Zeit: `{out_payload['generated_at']}`",
            f"- Git SHA: `{out_payload['git_sha']}`",
            f"- Anzahl gepruefter Assets: `{out_payload['assets_checked']}`",
            "",
            "## PASS/WARN/FAIL/UNKNOWN pro Asset",
            "",
        ]
        for symbol, status in out_payload["status_by_asset"].items():
            lines.append(f"- `{symbol}`: `{status}`")
        lines.extend(["", "## Haeufigste Datenfehler", ""])
        for reason, count in out_payload["top_data_errors"]:
            lines.append(f"- `{reason}`: `{count}`")
        lines.extend(["", "## Live-Blocker", ""])
        if out_payload["live_blockers"]:
            lines.extend(f"- `{symbol}`" for symbol in out_payload["live_blockers"])
        else:
            lines.append("- Keine Live-Blocker erkannt.")
        lines.extend(["", "## Naechste Schritte", ""])
        lines.extend(f"- {step}" for step in out_payload["next_steps"])
        lines.extend(["", "## Deutsche Zusammenfassung fuer Philipp", ""])
        lines.extend(f"- {item}" for item in out_payload["summary_de"])
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text("\n".join(lines), encoding="utf-8")

    print(
        "market_data_quality_report: "
        f"assets={out_payload['assets_checked']} "
        f"live_blockers={len(out_payload['live_blockers'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
