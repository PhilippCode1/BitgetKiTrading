#!/usr/bin/env python3
"""
Coverage-Gates nach `coverage run` (Unit; optional mit `coverage run -a` Integration):

1) shared_py (gesamt, Zeilen): --include=**/shared_py/**
   --fail-under=SHARED_PY_MIN
2) shared_py/resilience/ (Kernpfad, Zeilen): --fail-under=CORE_PATH_MIN
3) live_broker (Gesamt, Zeilen): --include=**/live_broker/**
   --fail-under=LIVE_BROKER_MIN
4) signal_engine/scoring/ (Kernpfad, Zeilen): --fail-under=CORE_PATH_MIN
5) live_broker/execution/ (Kernpfad, Zeilen): --fail-under=CORE_PATH_MIN
6) CRITICAL_SUFFIXES: aggregierte Zeilen-Deckung >= CRITICAL_MIN
7) HIGH_RISK_SUFFIXES: aggregierte Zeilen-Deckung >= HIGH_RISK_MIN
   (Kern an Börse/Reconcile)

Aufruf vom Repo-Root: python tools/check_coverage_gates.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Order-Submit-Persistenz (orders/service.py) bewusst nicht im kritischen Kern-Gate
# (sehr gross; separat durch tests/unit/live_broker abgedeckt).
CRITICAL_SUFFIXES = (
    "shared_py/risk_engine.py",
    "shared_py/leverage_allocator.py",
    "shared_py/exit_engine.py",
    "shared_py/observability/execution_forensic.py",
    "paper_broker/strategy/gating.py",
    "signal_engine/scoring/risk_score.py",
    "signal_engine/scoring/rejection_rules.py",
    "signal_engine/uncertainty.py",
    "live_broker/execution/service.py",
    "live_broker/execution/risk_adapter.py",
    "live_broker/execution/models.py",
    "live_broker/exchange_client.py",
    "monitor_engine/alerts/trading_sql_alerts.py",
)

# Erweiterte Risiko-Module (REST, Reconcile, Divergenz-Protokoll)
HIGH_RISK_SUFFIXES = (
    "shared_py/shadow_live_divergence.py",
    "live_broker/private_rest.py",
    "live_broker/reconcile/service.py",
)

# Volles shared_py inkl. Bitget-HTTP/Model-Contract — CI-Gesamtlauf typisch ~80 %+.
SHARED_PY_FAIL_UNDER = 80
LIVE_BROKER_FAIL_UNDER = 62
# Kernpfad-Verzeichnisse (resilience, scoring, execution) — blockierend in CI
CORE_PATH_MIN = 90.0
CRITICAL_MIN = 90.0
HIGH_RISK_MIN = 81.0

# Reihenfolge: nach shared-Paket, vor/ um live_broker-Gesamtschwelle
_CORE_PATH_GATES: tuple[tuple[str, str], ...] = (
    ("shared_py/resilience", "**/shared_py/resilience/**"),
    ("signal_engine/scoring", "**/signal_engine/scoring/**"),
    ("live_broker/execution", "**/live_broker/execution/**"),
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _aggregate_line_percent(
    files: dict,
    suffixes: tuple[str, ...],
) -> tuple[float, list[tuple[str, float, int, int]], list[str]]:
    details: list[tuple[str, float, int, int]] = []
    cl = sl = 0
    missing: list[str] = []
    for suf in suffixes:
        found = False
        for path, payload in files.items():
            n = _norm(path)
            if not n.endswith(suf):
                continue
            found = True
            summary = (payload or {}).get("summary") or {}
            stmts = int(summary.get("num_statements") or 0)
            covered = int(summary.get("covered_lines") or 0)
            if stmts <= 0:
                continue
            pct = 100.0 * covered / stmts
            cl += covered
            sl += stmts
            details.append((n, pct, covered, stmts))
        if not found:
            missing.append(suf)
    if sl <= 0:
        return 0.0, details, missing
    return 100.0 * cl / sl, details, missing


def main() -> int:
    root = _root()
    env = {**os.environ, "PYTHONUTF8": os.environ.get("PYTHONUTF8", "1")}

    r1 = subprocess.run(
        [
            "coverage",
            "report",
            "--include=**/shared_py/**",
            f"--fail-under={SHARED_PY_FAIL_UNDER}",
        ],
        cwd=root,
        env=env,
    )
    if r1.returncode != 0:
        return r1.returncode

    for i, (label, inc) in enumerate(_CORE_PATH_GATES, start=1):
        r_core = subprocess.run(
            [
                "coverage",
                "report",
                f"--include={inc}",
                f"--fail-under={int(CORE_PATH_MIN)}",
            ],
            cwd=root,
            env=env,
        )
        if r_core.returncode != 0:
            print(
                f"FAIL: Kernpfad-Gate «{label}» unter {CORE_PATH_MIN}%.",
                file=sys.stderr,
            )
            return 6 + i  # 7, 8, 9

    r2 = subprocess.run(
        [
            "coverage",
            "report",
            "--include=**/live_broker/**",
            f"--fail-under={LIVE_BROKER_FAIL_UNDER}",
        ],
        cwd=root,
        env=env,
    )
    if r2.returncode != 0:
        return r2.returncode

    subprocess.run(
        ["coverage", "json", "-o", str(root / "coverage.json")],
        cwd=root,
        env=env,
        check=True,
    )
    data = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
    files = data.get("files") or {}

    present_critical = {
        suf for suf in CRITICAL_SUFFIXES for p in files if _norm(p).endswith(suf)
    }
    missing_crit = sorted(set(CRITICAL_SUFFIXES) - present_critical)
    if missing_crit:
        print(
            "check_coverage_gates: fehlende kritische Dateien in coverage:",
            file=sys.stderr,
        )
        for m in missing_crit:
            print(f"  */{m}", file=sys.stderr)
        return 3

    agg, details, _ = _aggregate_line_percent(files, CRITICAL_SUFFIXES)
    print(f"coverage gate critical (Zeilen): {agg:.2f}% (min {CRITICAL_MIN}%)")
    for path, pct, cov, stm in sorted(details):
        print(f"  {path}: {pct:.1f}% ({cov}/{stm} lines)")

    if agg + 1e-9 < CRITICAL_MIN:
        print("\nFAIL: kritische Module unter Schwelle.", file=sys.stderr)
        return 4

    hr_agg, hr_details, hr_missing = _aggregate_line_percent(files, HIGH_RISK_SUFFIXES)
    if hr_missing:
        print(
            "check_coverage_gates: fehlende High-Risk-Dateien in coverage:",
            file=sys.stderr,
        )
        for m in hr_missing:
            print(f"  */{m}", file=sys.stderr)
        return 5

    print(
        f"coverage gate high-risk (Zeilen): {hr_agg:.2f}% (min {HIGH_RISK_MIN}%)",
    )
    for path, pct, cov, stm in sorted(hr_details):
        print(f"  {path}: {pct:.1f}% ({cov}/{stm} lines)")

    if hr_agg + 1e-9 < HIGH_RISK_MIN:
        print("\nFAIL: High-Risk-Module unter Schwelle.", file=sys.stderr)
        return 6

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
