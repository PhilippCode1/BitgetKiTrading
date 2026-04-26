#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.liquidity_scoring import evaluate_liquidity_gate, liquidity_score_to_dict  # noqa: E402

DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"


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


def _load_assets(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = payload if isinstance(payload, list) else payload.get("assets", [])
    if not isinstance(assets, list):
        return []
    return [item for item in assets if isinstance(item, dict)]


def build_payload(input_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in _load_assets(input_path):
        result = evaluate_liquidity_gate(
            {
                "symbol": item.get("symbol"),
                "market_family": item.get("market_family", "futures"),
                "order_type": item.get("order_type", "market"),
                "requested_size": item.get("planned_qty"),
                "requested_notional": item.get("requested_notional"),
                "best_bid": item.get("bid"),
                "best_ask": item.get("ask"),
                "bids": item.get("bids"),
                "asks": item.get("asks"),
                "orderbook_depth_top_10": item.get("orderbook_depth_top_10", item.get("requested_notional", 0.0)),
                "timestamp_age_ms": item.get("orderbook_age_ms"),
                "max_orderbook_age_ms": item.get("max_orderbook_age_ms"),
                "estimated_slippage_bps": item.get("estimated_slippage_bps"),
                "min_depth_ratio": item.get("min_depth_ratio", 1.0),
                "tick_size": item.get("tick_size"),
                "lot_size": item.get("lot_size"),
                "min_qty": item.get("min_qty"),
                "min_notional": item.get("min_notional"),
                "precision": item.get("precision"),
                "runtime_data": bool(item.get("runtime_data", False)),
            }
        )
        row = liquidity_score_to_dict(result)
        row["asset"] = str(item.get("symbol") or "").upper()
        row["allowed_order_size"] = float(item.get("planned_qty") or 0.0) if result.live_allowed else 0.0
        row["blocked_order_size"] = 0.0 if result.live_allowed else float(item.get("planned_qty") or 0.0)
        rows.append(row)
    status = "not_enough_evidence"
    if rows and all(r.get("status") == "pass" and r.get("evidence_level") == "runtime" for r in rows):
        status = "verified"
    return {
        "checked_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "assets_checked": len(rows),
        "live_allowed_count": sum(1 for r in rows if r["live_allowed"]),
        "status": status if status != "verified" else "implemented",
        "decision": "not_enough_evidence" if status != "verified" else "verified",
        "evidence_level": "runtime" if rows and all(r["evidence_level"] == "runtime" for r in rows) else "synthetic",
        "assets": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Spread Slippage Evidence",
        "",
        f"- checked_at: `{payload['checked_at']}`",
        f"- git_sha: `{payload['git_sha']}`",
        f"- assets_checked: `{payload['assets_checked']}`",
        f"- live_allowed_count: `{payload['live_allowed_count']}`",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- evidence_level: `{payload['evidence_level']}`",
        "",
        "## Assets",
        "",
        "| Asset | Status | Spread bps | Slippage bps | Depth Score | Staleness ms | Live erlaubt | Gruende |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["assets"]:
        lines.append(
            "| {asset} | `{status}` | `{spread}` | `{slippage}` | `{depth}` | `{stale}` | `{live}` | `{reasons}` |".format(
                asset=row["asset"],
                status=row["status"],
                spread=row.get("spread_bps"),
                slippage=row.get("estimated_slippage_bps"),
                depth=row.get("depth_score"),
                stale=row.get("staleness_ms"),
                live=row["live_allowed"],
                reasons=", ".join(row.get("reasons", [])) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Einordnung",
            "",
            "- Ohne echte Runtime-Orderbookdaten bleibt die Entscheidung `not_enough_evidence`.",
            "- Synthetic/Test-Orderbooks sind kein Verified-Nachweis.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Erzeugt Liquidity/Spread/Slippage Evidence-Report.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = build_payload(args.input_json)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "liquidity_spread_slippage_evidence_report: "
        f"assets={payload['assets_checked']} live_allowed={payload['live_allowed_count']} decision={payload['decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
