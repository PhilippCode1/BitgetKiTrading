#!/usr/bin/env python3
"""Erzeugt einen Liquiditaets-/Spread-/Slippage-Report pro Asset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.liquidity_scoring import (  # noqa: E402
    build_liquidity_assessment,
    build_liquidity_block_reasons_de,
)

DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"


def _redact_secret_like_values(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw in value.items():
            k = str(key).lower()
            if any(token in k for token in ("secret", "token", "password", "key")):
                out[key] = "***REDACTED***"
            else:
                out[key] = _redact_secret_like_values(raw)
        return out
    if isinstance(value, list):
        return [_redact_secret_like_values(item) for item in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    if args.dry_run:
        print("liquidity_quality_report: dry-run=true (fixture/read-only)")
        print("planned_steps=load_fixture,score_liquidity,render_reports")
        return 0

    input_path = args.input_json or DEFAULT_INPUT
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    assets = payload if isinstance(payload, list) else payload.get("assets", [])
    assessed: list[dict[str, Any]] = []
    for item in assets:
        assessment = build_liquidity_assessment(
            symbol=str(item.get("symbol") or "UNKNOWN"),
            bid=item.get("bid"),
            ask=item.get("ask"),
            bids=list(item.get("bids") or []),
            asks=list(item.get("asks") or []),
            orderbook_age_ms=int(item.get("orderbook_age_ms") or 0),
            max_orderbook_age_ms=int(item.get("max_orderbook_age_ms") or 0),
            planned_qty=float(item.get("planned_qty") or 0.0),
            requested_notional=float(item.get("requested_notional") or 0.0),
            status=item.get("status"),
            owner_approved_small_size=bool(item.get("owner_approved_small_size")),
        )
        assessed.append(
            {
                "asset": assessment.symbol,
                "spread_bps": assessment.spread_bps,
                "slippage_buy_bps": assessment.slippage_buy_bps,
                "slippage_sell_bps": assessment.slippage_sell_bps,
                "depth_status": assessment.depth_status,
                "liquidity_tier": assessment.liquidity_tier,
                "max_recommended_notional": assessment.max_recommended_notional,
                "live_status": "LIVE_ALLOWED" if assessment.live_allowed else "LIVE_BLOCKED",
                "block_reasons": assessment.block_reasons,
                "block_reasons_de": build_liquidity_block_reasons_de(assessment.block_reasons),
            }
        )

    out_payload = _redact_secret_like_values({"assets": assessed})
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        lines = ["# Liquiditaets-Qualitaetsreport", ""]
        for row in assessed:
            lines.append(
                f"- `{row['asset']}` spread_bps={row['spread_bps']} "
                f"slippage_buy={row['slippage_buy_bps']} slippage_sell={row['slippage_sell_bps']} "
                f"tier={row['liquidity_tier']} max_notional={row['max_recommended_notional']} "
                f"live={row['live_status']}"
            )
            if row["block_reasons_de"]:
                lines.append("  - Blockgruende: " + "; ".join(row["block_reasons_de"]))
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"liquidity_quality_report: assets={len(assessed)} blocked={sum(1 for row in assessed if row['live_status']=='LIVE_BLOCKED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
