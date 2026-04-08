#!/usr/bin/env python3
"""
LLM-Eval-Regression: pytest tests/llm_eval (gleiche Suite wie CI python-Job).

Mit --write-report werden unter artifacts/llm_eval/ junit.xml und run_summary.json erzeugt
(Baseline-Id aus shared/prompts/eval_baseline.json, Exit-Code, Zeitstempel).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="LLM-Governance- und Eval-Regression (pytest tests/llm_eval).",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Schreibt artifacts/llm_eval/junit.xml und run_summary.json.",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        default=[],
        help="Zusätzliche Argumente an pytest (nach tests/llm_eval).",
    )
    args = parser.parse_args()

    report_dir = root / "artifacts" / "llm_eval"
    cmd: list[str] = [
        sys.executable,
        "-m",
        "pytest",
        "tests/llm_eval",
        "-q",
        "--tb=short",
    ]
    if args.write_report:
        report_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--junitxml", str(report_dir / "junit.xml")])

    cmd.extend(args.pytest_args)

    proc = subprocess.run(cmd, cwd=str(root))
    exit_code = int(proc.returncode)

    if args.write_report:
        baseline_path = root / "shared" / "prompts" / "eval_baseline.json"
        baseline_id = ""
        try:
            baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_id = str(baseline_data.get("baseline_id") or "")
        except (OSError, json.JSONDecodeError):
            baseline_id = ""

        summary = {
            "baseline_id": baseline_id,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "exit_code": exit_code,
            "pytest_command": cmd,
            "junit_xml_relative": "artifacts/llm_eval/junit.xml",
        }
        (report_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
