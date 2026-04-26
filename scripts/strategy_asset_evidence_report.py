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
    strategy_evidence_decision,
    strategy_evidence_live_allowed,
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
    checked_strategies: set[str] = set()
    checked_asset_classes: set[str] = set()
    checked_symbols: set[str] = set()
    for item in items:
        reasons = validate_strategy_asset_evidence(item)
        decision = strategy_evidence_decision(item)
        live_allowed = strategy_evidence_live_allowed(item)
        checked_strategies.add(item.strategy_id or "unknown")
        checked_asset_classes.add(item.asset_class)
        checked_symbols.add(item.asset_symbol)
        out.append(
            {
                "strategy": item.strategy_id,
                "version": item.strategy_version,
                "strategy_id": item.strategy_id,
                "strategy_version": item.strategy_version,
                "asset_symbol": item.asset_symbol,
                "asset_class": item.asset_class,
                "market_family": item.market_family,
                "symbols_tested": item.symbols_tested or [item.asset_symbol],
                "timeframe": item.timeframe,
                "test_start": item.test_start,
                "test_end": item.test_end,
                "data_source": item.data_source,
                "data_quality_status": item.data_quality_status,
                "fees_included": item.fees_included,
                "spread_included": item.spread_included,
                "slippage_included": item.slippage_included,
                "funding_included": item.funding_included,
                "leverage_assumption": item.leverage_assumption,
                "risk_per_trade": item.risk_per_trade,
                "max_position_size": item.max_position_size,
                "number_of_trades": item.number_of_trades,
                "win_rate": item.win_rate,
                "average_win": item.average_win,
                "average_loss": item.average_loss,
                "profit_factor": item.profit_factor,
                "expectancy": item.expectancy,
                "max_drawdown": item.max_drawdown,
                "longest_loss_streak": item.longest_loss_streak,
                "sharpe_or_sortino": item.sharpe_or_sortino,
                "out_of_sample_result": item.out_of_sample_result,
                "walk_forward_result": item.walk_forward_result,
                "paper_result": item.paper_result,
                "shadow_result": item.shadow_result,
                "known_failure_modes": item.known_failure_modes or [],
                "parameter_hash": item.parameter_hash,
                "model_parameters_reproducible": item.model_parameters_reproducible,
                "evidence_status": item.evidence_status,
                "evidence_level": item.evidence_level,
                "backtest_available": item.backtest_available,
                "walk_forward_available": item.walk_forward_available,
                "paper_available": item.paper_available,
                "shadow_available": item.shadow_available,
                "decision": decision,
                "live_allowed": live_allowed,
                "missing_evidence": reasons,
                "live_block_reasons": reasons,
                "summary_de": build_strategy_asset_evidence_summary_de(item),
                "checked_at": item.checked_at or _now(),
                "git_sha": item.git_sha or "unknown",
            }
        )
    status = "NOT_ENOUGH_EVIDENCE"
    if out and all(row["evidence_level"] in {"paper", "shadow", "runtime"} for row in out):
        status = "implemented"
    return {
        "generated_at": _now(),
        "status": status,
        "verified": False,
        "checked_strategies": sorted(checked_strategies),
        "checked_asset_classes": sorted(checked_asset_classes),
        "checked_symbols": sorted(checked_symbols),
        "items": out,
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Strategy-Asset-Evidence Report",
        "",
        f"- Generiert: {report['generated_at']}",
        f"- Gesamtstatus: {report['status']}",
        f"- Verified: {report['verified']}",
        f"- Gepruefte Strategien: {', '.join(report['checked_strategies'])}",
        f"- Gepruefte Asset-Klassen: {', '.join(report['checked_asset_classes'])}",
        f"- Gepruefte Symbole: {', '.join(report['checked_symbols'])}",
        "",
    ]
    for item in report["items"]:
        lines.extend(
            [
                f"## {item['strategy']} / {item['asset_symbol']}",
                f"- Version: {item['version']}",
                f"- Asset-Klasse: {item['asset_class']}",
                f"- Evidence-Status: {item['evidence_status']}",
                f"- Evidence-Level: {item['evidence_level']}",
                (
                    "- Backtest/Walk-forward/Paper/Shadow: "
                    f"{item['backtest_available']}/{item['walk_forward_available']}/"
                    f"{item['paper_available']}/{item['shadow_available']}"
                ),
                f"- Decision: {item['decision']}",
                f"- Live allowed: {item['live_allowed']}",
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
    parser.add_argument("--output-md", default="reports/strategy_asset_evidence.md")
    parser.add_argument("--output-json", default="reports/strategy_asset_evidence.json")
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
