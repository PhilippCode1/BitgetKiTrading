#!/usr/bin/env python3
"""Refreshes the Bitget asset universe catalog (fixture/read-only)."""

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

from shared_py.bitget.asset_universe import (  # noqa: E402
    BitgetAssetCatalogEntry,
    block_reasons_to_german,
    now_iso,
    summarize_asset_universe,
)

DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "bitget_asset_universe_sample.json"


def _redact_secret_like_values(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("secret", "token", "password", "key")):
                out[key] = "***REDACTED***"
            else:
                out[key] = _redact_secret_like_values(raw)
        return out
    if isinstance(value, list):
        return [_redact_secret_like_values(item) for item in value]
    return value


def load_entries_from_json(path: Path) -> list[BitgetAssetCatalogEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("assets", [])
    if not isinstance(items, list):
        raise ValueError("input-json muss eine Liste oder {'assets': [...]} enthalten.")
    validated: list[BitgetAssetCatalogEntry] = []
    for raw in items:
        entry = BitgetAssetCatalogEntry.model_validate(raw).with_evaluated_live_gate()
        validated.append(entry)
    return validated


def build_report_payload(entries: list[BitgetAssetCatalogEntry]) -> dict[str, Any]:
    summary = summarize_asset_universe(entries)
    return {
        "generated_at": now_iso(),
        "project": "bitget-btc-ai",
        "mode": "fixture_or_readonly",
        "summary": {
            "total_assets": summary.total_assets,
            "active_assets": summary.active_assets,
            "blocked_assets": summary.blocked_assets,
            "quarantined_assets": summary.quarantined_assets,
            "shadow_allowed_assets": summary.shadow_allowed_assets,
            "live_allowed_assets": summary.live_allowed_assets,
            "market_family_counts": summary.market_family_counts,
        },
        "assets": [
            {
                **entry.model_dump(mode="json"),
                "live_block_reasons_de": block_reasons_to_german(entry.live_block_reasons),
            }
            for entry in entries
        ],
        "external_readonly_evidence_required": True,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Bitget Asset Universe Refresh Report",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Projektname: `{payload['project']}`",
        f"- Modus: `{payload['mode']}`",
        "",
        "## Main-Console Asset-Universum",
        "",
        f"- Erkannte Assets: `{summary['total_assets']}`",
        f"- Aktive Assets: `{summary['active_assets']}`",
        f"- Blockierte Assets: `{summary['blocked_assets']}`",
        f"- In Quarantaene: `{summary['quarantined_assets']}`",
        f"- Shadow-faehig: `{summary['shadow_allowed_assets']}`",
        f"- Live-faehig: `{summary['live_allowed_assets']}`",
        "",
        "## Assets",
        "",
    ]
    for item in payload["assets"]:
        lines.append(
            f"- `{item['symbol']}` ({item['market_family']} / {item.get('product_type') or 'n/a'}) "
            f"status={item['status_on_exchange']} live_allowed={str(item['live_allowed']).lower()} "
            f"risk_tier={item['risk_tier']} liquidity_tier={item['liquidity_tier']} "
            f"data_quality={item['data_quality_status']}"
        )
        if item["live_block_reasons_de"]:
            lines.append("  - Blockgruende: " + "; ".join(item["live_block_reasons_de"]))
    lines.extend(
        [
            "",
            "## Hinweis",
            "",
            "- Dieser Report nutzt Fixture-/Read-only-Daten.",
            "- Echte Bitget-Read-only-Discovery-Evidence ist weiterhin extern erforderlich.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)

    if args.dry_run:
        print("refresh_bitget_asset_universe: dry-run=true (network=disabled, read-only-plan-only)")
        print("planned_steps=load_fixture,evaluate_live_gates,build_reports")
        return 0

    input_path = args.input_json or DEFAULT_INPUT
    entries = load_entries_from_json(input_path)
    payload = build_report_payload(entries)
    payload = _redact_secret_like_values(payload)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")

    print(
        "refresh_bitget_asset_universe: "
        f"assets={payload['summary']['total_assets']} "
        f"blocked={payload['summary']['blocked_assets']} "
        f"live_allowed={payload['summary']['live_allowed_assets']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
