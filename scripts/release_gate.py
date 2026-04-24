#!/usr/bin/env python3
"""
Release-Gate (P84 Iron Curtain) und Legacy-Pfad (Merge-/Smoke, weniger hart).

Iron Curtain (``--iron-curtain``):
  ENVIRONMENT=production muss gesetzt sein (P84), sonst Exit 1. Sequenz, kein
  Fehlertoleranz, ein Subfehler = Exit 1.
  1) Static: pnpm check-types, format:check, Ruff, Black, Mypy (CI-Parity)
  2) Safety: ENV-.example-Security, Schema-JSON-Fixture, Katalog/Contracts
     (check_contracts), MIGRATIONS vs. config/schema_master.hash, Secret-/Repo-Scan
     (release_sanity, kein Doppel-TS: ohne --include-dashboard-pnpm), eval-Baseline
  3) Logic: migrate + modul_mate (DB), voll DB-Haertung, pytest (ohne duplizierte
     Oracle-Datei), integration-pytest, Dashboard Jest (test:ci) — optional mit Coverage
  4) Invariants (P75): ``pytest shared/python/tests/test_runtime_safety_oracle.py``
  5) Runtime: rc_health_runner + stable-window-sec (standard 30s)
  6) Optional: Playwright (``--with-e2e``), Gateway/Dashboard laufen

  CI-Umgebung: cross-env wie in package.json, DATABASE_URL/REDIS_URL in Shell oder
  aus .env.production/.env.local (fehlende Keys nur dort nachgeladen, ohne ENVIRONMENT
  zu ueberschreiben).

Legacy: siehe ehemaliger Ablauf (Vorgates, selfcheck, Probes, optional E2E).

`docs/cursor_execution/07_ci_and_release_contract.md` — Abgleich.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print("==>", " ".join(str(x) for x in argv), flush=True)
    r = subprocess.run(
        [str(x) for x in argv], cwd=str(cwd), env=env or os.environ.copy()
    )
    return int(r.returncode)


def _load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        out[key] = val
    return out


def _hydrate_secrets_from_dotenvs(root: Path) -> None:
    """Nur leere Keys: DATABASE/REDIS/Test, damit lokal pnpm+Datei reicht."""
    keys = {
        "DATABASE_URL",
        "REDIS_URL",
        "TEST_DATABASE_URL",
        "TEST_REDIS_URL",
    }
    for name in (".env.production", ".env.local"):
        d = _load_dotenv_file(root / name)
        for k, v in d.items():
            if k not in keys or not (v or "").strip():
                continue
            if not (os.environ.get(k) or "").strip():
                os.environ[k] = v


def _iron_require_env() -> str | None:
    v = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    if v != "production":
        return (
            "IRON CURTAIN: Setze ENVIRONMENT=production (P84). "
            f"Aktuell: {os.environ.get('ENVIRONMENT', '')!r}"
        )
    return None


_RUFF_TARGETS: tuple[str, ...] = (
    "tests/unit",
    "tests/integration",
    "tests/signal_engine",
    "tests/shared",
    "tests/paper_broker",
    "tests/fixtures",
    "tests/conftest.py",
    "tests/integration/fixtures",
    "config/required_secrets.py",
    "config/bootstrap.py",
    "tools/check_schema.py",
    "tools/check_contracts.py",
    "tools/check_coverage_gates.py",
    "tools/release_sanity_checks.py",
    "tools/validate_env_profile.py",
    "tools/pip_audit_supply_chain_gate.py",
    "tools/check_production_env_template_security.py",
    "tools/modul_mate_selfcheck.py",
    "tools/production_selfcheck.py",
    "scripts/release_gate.py",
    "tools/local_stack_doctor.py",
    "tools/run_llm_eval.py",
    "tools/validate_eval_baseline.py",
    "tools/check_release_approval_gates.py",
    "tools/db_production_hardening.py",
)

_BLACK_TARGETS: tuple[str, ...] = (
    "tests/integration",
    "tests/signal_engine",
    "tests/shared",
    "tests/paper_broker",
    "tests/conftest.py",
    "tests/fixtures",
    "tools/check_schema.py",
    "tools/check_contracts.py",
    "tools/check_coverage_gates.py",
    "tools/release_sanity_checks.py",
    "tools/validate_env_profile.py",
    "tools/pip_audit_supply_chain_gate.py",
    "tools/check_production_env_template_security.py",
    "tools/modul_mate_selfcheck.py",
    "tools/production_selfcheck.py",
    "scripts/release_gate.py",
    "tools/local_stack_doctor.py",
    "tools/run_llm_eval.py",
    "tools/validate_eval_baseline.py",
    "tools/check_release_approval_gates.py",
    "tools/db_production_hardening.py",
)

_MYPY_TARGETS: tuple[str, ...] = (
    "src/shared_py/leverage_allocator.py",
    "src/shared_py/risk_engine.py",
    "src/shared_py/exit_engine.py",
    "src/shared_py/shadow_live_divergence.py",
    "src/shared_py/product_policy.py",
    "src/shared_py/modul_mate_db_gates.py",
    "src/shared_py/model_layer_contract.py",
)

_ORACLE = "shared/python/tests/test_runtime_safety_oracle.py"

_ORACLE_FLAGS = (f"--ignore={_ORACLE}",)


def _bin(name: str) -> str:
    w = shutil.which(name)
    if w:
        return w
    name_cmd = f"{name}.cmd"
    w2 = shutil.which(name_cmd)
    if w2:
        return w2
    return name


def _iron_curtain_main(
    root: Path,
    py: str,
    *,
    with_e2e: bool,
) -> int:
    if msg := _iron_require_env():
        print(msg, file=sys.stderr, flush=True)
        return 1
    _hydrate_secrets_from_dotenvs(root)
    pnpm = _bin("pnpm")
    for tool in ("ruff", "black", "mypy"):
        if not shutil.which(tool) and not shutil.which(f"{tool}.exe"):
            print(
                f"IRON CURTAIN: {tool} fehlt im PATH "
                "(z. B. pip install -r requirements-dev).",
                file=sys.stderr,
                flush=True,
            )
            return 1
    if not shutil.which("pnpm") and not shutil.which("pnpm.cmd"):
        print(
            "IRON CURTAIN: pnpm fehlt (Monorepo install).",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if not (root / "node_modules").is_dir():
        print(
            "IRON CURTAIN: pnpm install am Repo-Root fehlt.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    def _fail(phase: str) -> int:
        print(
            f"\nIRON CURTAIN: {phase} — FEHLGESCHLAGEN (Exit 1)",
            file=sys.stderr,
            flush=True,
        )
        return 1

    print(
        "\n======== IRON CURTAIN 1/6 — Static (TS+Format+Ruff/Black/Mypy) ========\n",
        flush=True,
    )
    if _run([pnpm, "run", "check-types"], cwd=root) != 0:
        return _fail("static check-types")
    if _run([pnpm, "run", "format:check"], cwd=root) != 0:
        return _fail("static format:check")
    if _run([_bin("ruff"), "check", *_RUFF_TARGETS], cwd=root) != 0:
        return _fail("static ruff")
    if _run([_bin("black"), "--check", *_BLACK_TARGETS], cwd=root) != 0:
        return _fail("static black")
    mypy_env = {**os.environ, "MYPY_FORCE_COLOR": "0"}
    if (
        _run(
            [py, "-m", "mypy", *_MYPY_TARGETS],
            cwd=root / "shared" / "python",
            env=mypy_env,
        )
        != 0
    ):
        return _fail("static mypy")

    print(
        "\n======== IRON CURTAIN 2/6 — Safety (Secrets, Schema, Contracts) ========\n",
        flush=True,
    )
    evpath = str(root / "tools" / "check_production_env_template_security.py")
    if _run([py, evpath], cwd=root) != 0:
        return _fail("safety env-template-security")
    if (
        _run(
            [
                py,
                str(root / "tools" / "check_schema.py"),
                "--schema",
                "infra/tests/schemas/signals_recent_response.schema.json",
                "--json_file",
                "tests/fixtures/signals_fixture.json",
            ],
            cwd=root,
        )
        != 0
    ):
        return _fail("safety check_schema fixture")
    if _run([py, str(root / "tools" / "check_contracts.py")], cwd=root) != 0:
        return _fail("safety check_contracts")
    if (
        _run(
            [
                py,
                str(root / "tools" / "db_production_hardening.py"),
                "--migrations-fingerprint-only",
            ],
            cwd=root,
        )
        != 0
    ):
        return _fail("safety schema_master MIGRATIONS")
    if _run([py, str(root / "tools" / "validate_eval_baseline.py")], cwd=root) != 0:
        return _fail("safety eval baseline")
    if _run([py, str(root / "tools" / "release_sanity_checks.py")], cwd=root) != 0:
        return _fail("safety release_sanity (Secrets/Ballast)")

    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    rurl = (os.environ.get("REDIS_URL") or "").strip()
    if not dsn or not rurl:
        return _fail(
            "Logic: IRON CURTAIN erfordert DATABASE_URL + REDIS_URL "
            "(ENV oder .env.production/.env.local)"
        )

    print(
        "\n======== IRON CURTAIN 2b — DB: migrate, Modul-Mate, Haertung ========\n",
        flush=True,
    )
    menv: dict[str, str] = {**os.environ, "DATABASE_URL": dsn}
    if _run([py, str(root / "infra" / "migrate.py")], cwd=root, env=menv) != 0:
        return _fail("db migrate")
    mm = str(root / "tools" / "modul_mate_selfcheck.py")
    if _run([py, mm], cwd=root, env=menv) != 0:
        return _fail("db modul_mate_selfcheck")
    dbh = str(root / "tools" / "db_production_hardening.py")
    if _run([py, dbh], cwd=root, env=menv) != 0:
        return _fail("db production_hardening (Ping, LIVE_APP_SCHEMA, seeds)")

    cov_s = (os.environ.get("IRON_CURTAIN_COVERAGE") or "1").strip().lower()
    use_cov = cov_s not in ("0", "false", "off", "no")
    pye = {**os.environ, "CI": "true", "DATABASE_URL": dsn, "REDIS_URL": rurl}
    turl = (os.environ.get("TEST_DATABASE_URL") or dsn).strip()
    trurl = (os.environ.get("TEST_REDIS_URL") or "").strip()
    if not trurl and rurl.rstrip().endswith("/0"):
        trurl = rurl.rstrip()[:-1] + "1"
    elif not trurl:
        trurl = rurl
    pyei = {**pye, "TEST_DATABASE_URL": turl, "TEST_REDIS_URL": trurl}

    print(
        "\n======== IRON CURTAIN 3/6 — Logic: pytest+int+Jest) ========\n",
        flush=True,
    )
    base_py = [
        py,
        "-m",
        "pytest",
        "tests",
        "shared/python/tests",
        "services/onchain-sniffer/tests",
        "-m",
        "not",
        "integration",
        "-q",
        *_ORACLE_FLAGS,
    ]
    int_py = [
        py,
        "-m",
        "pytest",
        "tests/integration",
        "tests/learning_engine",
        "-m",
        "integration",
        "-q",
    ]

    if use_cov:
        if _run([py, "-m", "coverage", "erase"], cwd=root) != 0:
            return _fail("logic coverage erase")
        c1 = [py, "-m", "coverage", "run", "-m", *base_py[2:]]
        if _run(c1, cwd=root, env=pye) != 0:
            return _fail("logic pytest unit (coverage)")
        c2 = [py, "-m", "coverage", "run", "-a", "-m", *int_py[2:]]
        if _run(c2, cwd=root, env=pyei) != 0:
            return _fail("logic pytest integration (coverage)")
        if _run([py, str(root / "tools" / "check_coverage_gates.py")], cwd=root) != 0:
            return _fail("logic check_coverage_gates")
    else:
        if _run(base_py, cwd=root, env=pye) != 0:
            return _fail("logic pytest not-integration")
        if _run(int_py, cwd=root, env=pyei) != 0:
            return _fail("logic pytest integration")

    dash = root / "apps" / "dashboard" / "package.json"
    if not dash.is_file():
        return _fail("apps/dashboard fehlt")
    if _run([pnpm, "--dir", "apps/dashboard", "run", "test:ci"], cwd=root) != 0:
        return _fail("logic dashboard jest (test:ci)")

    p4 = f"\n======== IRON CURTAIN 4/6 — Invariants P75: {_ORACLE} ========\n"
    print(p4, flush=True)
    if (
        _run(
            [py, "-m", "pytest", _ORACLE, "-q"],
            cwd=root,
            env=pye,
        )
        != 0
    ):
        return _fail("invariants RuntimeSafetyOracle")

    stable = (os.environ.get("IRON_CURTAIN_STABLE_WINDOW_SEC") or "30").strip() or "30"
    p5 = f"\n======== IRON CURTAIN 5/6 — rc:health stable={stable} ========\n"
    print(p5, flush=True)
    env_local = root / ".env.local"
    if not env_local.is_file():
        return _fail("Runtime: .env.local fehlt (Edge-URL/Gateway-Health)")
    rc = [
        py,
        str(root / "scripts" / "rc_health_runner.py"),
        str(env_local),
        "--stable-window-sec",
        str(stable),
    ]
    if _run(rc, cwd=root) != 0:
        return _fail("runtime rc_health (stable)")

    if with_e2e:
        pnpm2 = _bin("pnpm")
        e2e_url = (
            os.environ.get("E2E_BASE_URL")
            or os.environ.get("DASHBOARD_BASE_URL")
            or "http://127.0.0.1:3000"
        ).strip()
        eenv = {**os.environ, "E2E_BASE_URL": e2e_url}
        print("\n======== IRON CURTAIN 6/6 — Playwright E2E ========\n", flush=True)
        rc2 = subprocess.run(
            [pnpm2, "exec", "playwright", "test", "-c", "e2e/playwright.config.ts"],
            cwd=str(root),
            env=eenv,
        )
        if int(rc2.returncode) != 0:
            return _fail("e2e Playwright")
    else:
        print("==> SKIP E2E (ohne --with-e2e)", flush=True)

    print("\nIRON CURTAIN: ALLE PRUEFUNGEN OK (Exit 0)\n", flush=True)
    return 0


def legacy_main(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    py = sys.executable
    failed = False

    with_e2e = args.with_e2e or os.environ.get("PLAYWRIGHT_E2E", "").strip() == "1"

    for script in (
        "check_production_env_template_security.py",
        "check_contracts.py",
    ):
        if _run([py, str(root / "tools" / script)], cwd=root) != 0:
            print(
                f"\nRELEASE GATE: FEHLGESCHLAGEN ({script})",
                file=sys.stderr,
            )
            return 1

    if (
        _run(
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

    if _run([py, str(root / "tools" / "production_selfcheck.py")], cwd=root) != 0:
        print("\nRELEASE GATE: FEHLGESCHLAGEN (production_selfcheck)", file=sys.stderr)
        return 1

    env_local = root / ".env.local"
    skip_stack = os.environ.get("SKIP_STACK_SMOKES", "").strip() == "1"

    if not env_local.is_file():
        print(
            "WARN: .env.local fehlt — api_integration_smoke wird scheitern.",
            file=sys.stderr,
        )

    if _run([py, str(root / "scripts" / "api_integration_smoke.py")], cwd=root) != 0:
        failed = True

    if env_local.is_file() and not skip_stack:
        rc_health = [py, str(root / "scripts" / "rc_health_runner.py"), str(env_local)]
        if _run(rc_health, cwd=root) != 0:
            failed = True
        if (
            _run(
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
            _run(
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
        pnp = shutil.which("pnpm") or shutil.which("pnpm.cmd")
        if not pnp:
            print("E2E angefordert aber pnpm nicht gefunden", file=sys.stderr)
            failed = True
        else:
            e2e_url = (
                os.environ.get("E2E_BASE_URL")
                or os.environ.get("DASHBOARD_BASE_URL")
                or "http://127.0.0.1:3000"
            ).strip()
            env = {**os.environ, "E2E_BASE_URL": e2e_url}
            rcpw = subprocess.run(
                [pnp, "exec", "playwright", "test", "-c", "e2e/playwright.config.ts"],
                cwd=str(root),
                env=env,
            ).returncode
            if rcpw != 0:
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


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    py = sys.executable
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--iron-curtain",
        action="store_true",
        help="P84: harter Release-Lauf; erfordert ENVIRONMENT=production",
    )
    ap.add_argument(
        "--with-e2e",
        action="store_true",
        help="Playwright (e2e/tests/*.spec.ts) — Iron Curtain: optional Phase 6",
    )
    args = ap.parse_args()
    if args.iron_curtain:
        return _iron_curtain_main(root, py, with_e2e=args.with_e2e)
    return legacy_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
