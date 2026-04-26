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

from shared_py.multi_asset_strategy_evidence import (  # noqa: E402
    MultiAssetStrategyEvidence,
    evaluate_multi_asset_strategy_evidence,
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_items(path: Path) -> list[MultiAssetStrategyEvidence]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw["items"] if isinstance(raw, dict) else raw
    return [MultiAssetStrategyEvidence(**row) for row in rows]


def _build_report(items: list[MultiAssetStrategyEvidence]) -> dict[str, Any]:
    out_items: list[dict[str, Any]] = []
    summary = {"PASS": 0, "PASS_WITH_WARNINGS": 0, "FAIL": 0}
    reasons_global: list[str] = []
    strategy_versions: set[tuple[str, str]] = set()
    market_family_by_strategy: dict[str, set[str]] = {}
    asset_classes: set[str] = set()
    for item in items:
        verdict, reasons, text = evaluate_multi_asset_strategy_evidence(item)
        if not item.strategy_version:
            reasons.append("strategy_version_fehlt")
        if item.trade_count < 30:
            reasons.append("trade_count_unter_minimum")
        strategy_versions.add((item.strategy_id, item.strategy_version))
        market_family_by_strategy.setdefault(item.strategy_id, set()).add(item.market_family)
        asset_classes.add(item.asset_class)
        if reasons:
            verdict = "FAIL"
        reasons_global.extend(reasons)
        summary[verdict] += 1
        out_items.append(
            {
                "strategy_id": item.strategy_id,
                "strategy_version": item.strategy_version,
                "asset_symbol": item.asset_symbol,
                "asset_class": item.asset_class,
                "market_family": item.market_family,
                "verdict": verdict,
                "blockgruende_de": reasons,
                "entscheidung_de": text,
                "live_allowed": verdict == "PASS",
            }
        )
    for strategy_id, families in market_family_by_strategy.items():
        if len(families) > 1:
            summary["FAIL"] += 1
            reasons_global.append(f"market_family_mix_verboten:{strategy_id}")
    drift_guard = len(strategy_versions) == len({f"{sid}:{ver}" for sid, ver in strategy_versions})
    status = "NOT_ENOUGH_EVIDENCE"
    if summary["FAIL"] == 0 and summary["PASS"] > 0:
        status = "implemented"
    return {
        "generated_at": _now(),
        "status": status,
        "verified": False,
        "asset_classes_covered": sorted(asset_classes),
        "version_binding_ok": drift_guard,
        "global_block_reasons": sorted(set(reasons_global)),
        "summary": summary,
        "items": out_items,
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Multi-Asset Strategy Performance Evidence",
        "",
        f"- Generiert: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Verified: `{report['verified']}`",
        f"- Version-Bindung ok: `{report['version_binding_ok']}`",
        f"- PASS: `{report['summary']['PASS']}`",
        f"- PASS_WITH_WARNINGS: `{report['summary']['PASS_WITH_WARNINGS']}`",
        f"- FAIL: `{report['summary']['FAIL']}`",
        "",
    ]
    for item in report["items"]:
        lines.extend(
            [
                f"## {item['strategy_id']} / {item['asset_symbol']}",
                f"- Asset-Klasse: `{item['asset_class']}`",
                f"- Market-Family: `{item['market_family']}`",
                f"- Bewertung: `{item['verdict']}`",
                f"- Entscheidung (de): {item['entscheidung_de']}",
                "- Blockgründe (de): "
                + (", ".join(item["blockgruende_de"]) if item["blockgruende_de"] else "keine"),
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueft Multi-Asset Strategy-Performance-Evidence.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-json", default="tests/fixtures/multi_asset_strategy_evidence_sample.json")
    parser.add_argument("--output-md")
    parser.add_argument("--output-json")
    parser.add_argument("--allow-failures", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print("verify_multi_asset_strategy_evidence: dry-run=true network_calls=0 no_orders=true")
        return 0

    items = _load_items(Path(args.input_json))
    report = _build_report(items)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))

    if args.output_md:
        out_md = Path(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(_to_md(report), encoding="utf-8")
    if args.output_json:
        out_json = Path(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    if args.allow_failures:
        return 0
    return 0 if report["summary"]["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
