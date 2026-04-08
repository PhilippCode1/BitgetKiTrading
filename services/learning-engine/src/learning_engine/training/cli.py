from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[5]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        s = str(p)
        if p.is_dir() and s not in sys.path:
            sys.path.insert(0, s)


_ensure_paths()

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.training.pipeline import run_training_jobs

logger = logging.getLogger("learning_engine.training.cli")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Learning-Engine Trainingspipeline (reproduzierbar)")
    p.add_argument(
        "job",
        choices=("take-trade", "expected-bps", "regime", "specialists-audit", "all"),
        help="Trainingsjob (specialists-audit: nur Readiness-JSON, kein Training)",
    )
    p.add_argument("--symbol", default=None, help="z.B. <example_symbol>")
    p.add_argument("--no-promote", action="store_true", help="Kein promoted_bool in Registry")
    p.add_argument(
        "--summary-out",
        default=None,
        help="Optional: JSON-Datei mit Pipeline-Ergebnis-Stub (run_id, artifact_path, …)",
    )
    args = p.parse_args(argv)
    promote = not args.no_promote
    settings = LearningEngineSettings()
    with db_connect(settings.database_url) as conn:
        with conn.transaction():
            summary = run_training_jobs(
                conn,
                settings,
                args.job,
                symbol=args.symbol,
                promote=promote,
            )
    if args.summary_out:
        Path(args.summary_out).write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )
    logger.info("training ok")
    return 0
