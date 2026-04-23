#!/usr/bin/env python3
"""
Release-Gate: HTTP-Smokes (Gateway), optional RC-Health + KI-Orchestrator,
Dashboard-HTML-Probes, optional Playwright-E2E (Nutzerreisen).

Ablauf (hart, Exit 1 bei Fehler):
  1) check_production_env_template_security.py
  2) check_contracts.py
  3) release_sanity_checks.py --include-dashboard-pnpm
  4) production_selfcheck.py
  5) API-Integration, Health, Probes, optional E2E

Zusaetzlich enthaelt production_selfcheck die gleichen Contract-/Env-Gates
(redundante Absicherung).

Qualitaetsvertrag Merge vs. Release:
docs/cursor_execution/07_ci_and_release_contract.md

Standard (lokal, .env.local vorhanden):
  python scripts/release_gate.py

Mit Browser-E2E (Dashboard muss erreichbar sein, z. B. Compose :3000):
  python scripts/release_gate.py --with-e2e

Umgebung:
  SKIP_DASHBOARD_PROBE=1     — dashboard_page_probe ueberspringen
  SKIP_STACK_SMOKES=1        — rc_health_runner + verify_ai ueberspringen
  DASHBOARD_BASE_URL         — Default http://127.0.0.1:3000 fuer Probes
  E2E_BASE_URL               — Playwright (Default wie Dashboard-URL)
  PLAYWRIGHT_E2E=1           — E2E wie --with-e2e (Kompatibilitaet)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print("==>", " ".join(argv), flush=True)
    r = subprocess.run(argv, cwd=str(cwd), env=env)
    return int(r.returncode)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    py = sys.executable
    failed = False

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--with-e2e",
        action="store_true",
        help="Playwright Release-Gate (e2e/tests/release-gate.spec.ts) ausfuehren",
    )
    args = ap.parse_args()
    with_e2e = args.with_e2e or os.environ.get("PLAYWRIGHT_E2E", "").strip() == "1"

    # Harte Vorgates (unabhaengig von production_selfcheck; keine Fehler verschlucken)
    for script in (
        "check_production_env_template_security.py",
        "check_contracts.py",
    ):
        if run([py, str(root / "tools" / script)], cwd=root) != 0:
            print(
                f"\nRELEASE GATE: FEHLGESCHLAGEN ({script})",
                file=sys.stderr,
            )
            return 1

    if (
        run(
            [
                py,
                str(root / "tools" / "release_sanity_checks.py"),
                "--include-dashboard-pnpm",
            ],
            cwd=root,
        )
        != 0
    ):
        print(
            "\nRELEASE GATE: FEHLGESCHLAGEN "
            "(release_sanity_checks, inkl. Dashboard tsc/jest/locale)",
            file=sys.stderr,
        )
        return 1

    if run([py, str(root / "tools" / "production_selfcheck.py")], cwd=root) != 0:
        print("\nRELEASE GATE: FEHLGESCHLAGEN (production_selfcheck)", file=sys.stderr)
        return 1

    env_local = root / ".env.local"
    skip_stack = os.environ.get("SKIP_STACK_SMOKES", "").strip() == "1"

    if not env_local.is_file():
        print(
            "WARN: .env.local fehlt — api_integration_smoke wird scheitern.",
            file=sys.stderr,
        )

    if run([py, str(root / "scripts" / "api_integration_smoke.py")], cwd=root) != 0:
        failed = True

    if env_local.is_file() and not skip_stack:
        rc_health = [
            py,
            str(root / "scripts" / "rc_health_runner.py"),
            str(env_local),
        ]
        if run(rc_health, cwd=root) != 0:
            failed = True
        if (
            run(
                [
                    py,
                    str(root / "scripts" / "verify_ai_operator_explain.py"),
                    "--env-file",
                    str(env_local),
                    "--mode",
                    "orchestrator",
                ],
                cwd=root,
            )
            != 0
        ):
            failed = True
    else:
        if skip_stack:
            print("==> SKIP rc_health + KI-Smoke (SKIP_STACK_SMOKES=1)", flush=True)
        else:
            print("==> SKIP rc_health + KI-Smoke (keine .env.local)", flush=True)

    if os.environ.get("SKIP_DASHBOARD_PROBE", "").strip() != "1":
        base = (os.environ.get("DASHBOARD_BASE_URL") or "http://127.0.0.1:3000").strip()
        if (
            run(
                [
                    py,
                    str(root / "scripts" / "dashboard_page_probe.py"),
                    "--base-url",
                    base,
                ],
                cwd=root,
            )
            != 0
        ):
            failed = True
    else:
        print("==> SKIP dashboard_page_probe (SKIP_DASHBOARD_PROBE=1)", flush=True)

    if with_e2e:
        pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
        if not pnpm:
            print("E2E angefordert aber pnpm nicht gefunden", file=sys.stderr)
            failed = True
        else:
            e2e_url = (
                os.environ.get("E2E_BASE_URL")
                or os.environ.get("DASHBOARD_BASE_URL")
                or "http://127.0.0.1:3000"
            ).strip()
            env = {**os.environ, "E2E_BASE_URL": e2e_url}
            rc = subprocess.run(
                [pnpm, "exec", "playwright", "test", "-c", "e2e/playwright.config.ts"],
                cwd=str(root),
                env=env,
            ).returncode
            if rc != 0:
                failed = True
    else:
        print(
            "==> SKIP Playwright "
            "(python scripts/release_gate.py --with-e2e zum Aktivieren)",
            flush=True,
        )

    if failed:
        print("\nRELEASE GATE: FEHLGESCHLAGEN", file=sys.stderr)
        return 1
    print("\nRELEASE GATE: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
