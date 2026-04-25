#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.strategy_asset_evidence import (
    StrategyAssetEvidence,
    build_strategy_asset_evidence_summary_de,
    validate_strategy_asset_evidence,
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_items(path: Path) -> list[StrategyAssetEvidence]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("items", [])
    return [StrategyAssetEvidence(**row) for row in rows]


def _to_json(items: list[StrategyAssetEvidence]) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for item in items:
        reasons = validate_strategy_asset_evidence(item)
        out.append(
            {
                "strategy": item.strategy_id,
                "version": item.strategy_version,
                "asset_symbol": item.asset_symbol,
                "asset_class": item.asset_class,
                "evidence_status": item.evidence_status,
                "backtest_available": item.backtest_available,
                "walk_forward_available": item.walk_forward_available,
                "paper_available": item.paper_available,
                "shadow_available": item.shadow_available,
                "missing_evidence": reasons,
                "live_block_reasons": reasons,
                "summary_de": build_strategy_asset_evidence_summary_de(item),
            }
        )
    return {"generated_at": _now(), "items": out}


def _to_markdown(report: dict[str, Any]) -> str:
    lines = ["# Strategy-Asset-Evidence Report", "", f"- Generiert: {report['generated_at']}", ""]
    for item in report["items"]:
        lines.extend(
            [
                f"## {item['strategy']} / {item['asset_symbol']}",
                f"- Version: {item['version']}",
                f"- Asset-Klasse: {item['asset_class']}",
                f"- Evidence-Status: {item['evidence_status']}",
                (
                    "- Backtest/Walk-forward/Paper/Shadow: "
                    f"{item['backtest_available']}/{item['walk_forward_available']}/"
                    f"{item['paper_available']}/{item['shadow_available']}"
                ),
                f"- Fehlende Evidence: {', '.join(item['missing_evidence']) if item['missing_evidence'] else 'keine'}",
                f"- Live-Blockgruende: {', '.join(item['live_block_reasons']) if item['live_block_reasons'] else 'keine'}",
                f"- Zusammenfassung: {item['summary_de']}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Erzeugt Strategy-Asset-Evidence-Report.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", default="tests/fixtures/strategy_asset_evidence_sample.json")
    parser.add_argument("--output-md", default="reports/strategy_asset_evidence_sample.md")
    parser.add_argument("--output-json", default="reports/strategy_asset_evidence_sample.json")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    items = _load_items(input_path)
    report = _to_json(items)
    if args.dry_run:
        print(
            f"strategy_asset_evidence_report: dry-run ok "
            f"(items={len(report['items'])}, input={input_path.as_posix()})"
        )
        return 0

    output_md = Path(args.output_md)
    output_json = Path(args.output_json)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_to_markdown(report), encoding="utf-8")
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        "strategy_asset_evidence_report: ok "
        f"(items={len(report['items'])}, md={output_md.as_posix()}, json={output_json.as_posix()})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
