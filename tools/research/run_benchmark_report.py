#!/usr/bin/env python3
"""Research: Benchmark-Evidence-Report (trade_evaluations + e2e_decision_records).

Schreibt JSON + Markdown unter RESEARCH_BENCHMARK_ARTIFACTS_DIR
(siehe .env.example).

Beispiel:
  python tools/research/run_benchmark_report.py
  python tools/research/run_benchmark_report.py \\
    --symbol BTCUSDT --limit-eval 500 --limit-e2e 200
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services/learning-engine/src"))
sys.path.insert(0, str(REPO / "shared/python/src"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default=None, help="Optional; sonst Universum")
    p.add_argument(
        "--limit-eval",
        type=int,
        default=None,
        help="Stichprobe learn.trade_evaluations",
    )
    p.add_argument(
        "--limit-e2e",
        type=int,
        default=None,
        help="Stichprobe learn.e2e_decision_records",
    )
    p.add_argument(
        "--stdout-json",
        action="store_true",
        help="Nur JSON auf stdout, keine Dateien",
    )
    args = p.parse_args()

    from learning_engine.config import LearningEngineSettings
    from learning_engine.research.harness import (
        build_benchmark_evidence_report,
        report_to_markdown,
    )
    from learning_engine.storage.connection import db_connect
    from learning_engine.storage.repo_backtest import (
        fetch_trade_evaluations_benchmark_sample,
    )
    from learning_engine.storage.repo_e2e import fetch_e2e_records_benchmark_sample

    settings = LearningEngineSettings()
    lim_ev = args.limit_eval or settings.research_benchmark_default_eval_limit
    lim_e2 = args.limit_e2e or settings.research_benchmark_default_e2e_limit
    lim_ev = max(1, min(int(lim_ev), 50_000))
    lim_e2 = max(1, min(int(lim_e2), 50_000))
    sym = args.symbol.strip().upper() if args.symbol and args.symbol.strip() else None

    with db_connect(settings.database_url) as conn:
        ev_rows = fetch_trade_evaluations_benchmark_sample(
            conn,
            symbol=sym,
            limit=lim_ev,
        )
        e2e_rows = fetch_e2e_records_benchmark_sample(
            conn,
            symbol=sym,
            limit=lim_e2,
        )

    report = build_benchmark_evidence_report(
        evaluation_rows=ev_rows,
        e2e_rows=e2e_rows,
        symbol_filter=sym,
        limit_evaluations=lim_ev,
        limit_e2e=lim_e2,
    )

    if args.stdout_json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    out_dir = Path(settings.research_benchmark_artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    sym_part = f"_{sym}" if sym else "_all"
    base = out_dir / f"benchmark_evidence{sym_part}_{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    print(str(json_path))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
