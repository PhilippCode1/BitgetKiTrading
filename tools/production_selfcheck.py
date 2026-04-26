#!/usr/bin/env python3
"""
Zentraler Produktions-Selfcheck (ohne Docker): Modul-Mate-Gates, Shared-Policy-Tests,
Live-Broker-Gate-Tests, Modell-Schicht-Vertrag (model_layer_contract), dann
tools/check_contracts.py, tools/check_schema.py und
check_production_env_template_security.py (Prod/Shadow-.example, wie CI).
Zusaetzlich: .env.local.example mit CI-Platzhalter-Ersatz durch validate_env_profile
(local), falls die Datei existiert.

Bei ``APP_ENV=production`` (streng, Prompt 35): nach bestandenem modul_mate_selfcheck
PFLICHT ``DATABASE_URL`` und sofort ``tools/db_production_hardening.py``
(DB-Ping, MIGRATIONS-Hash, LIVE_APP_SCHEMA, Seed-Lock).
Bei sonst profilbedingt prod-aehnlichem Lauf (PRODUCTION, ``APP_ENV`` staging|shadow
oder SELFCHECK_DATABASE_REQUIRED): ``db_production_hardening`` wie bisher, analog
``pnpm run config:validate:production`` (validate_env_profile, production ohne DB-SKIP).

Vor Pytest: `ruff check` auf den Selfcheck-Pfaden; `black --check` auf
den Tools + tests/shared/test_model_layer_contract.py (wie CI, ohne Legacy-tests/unit);
`mypy` auf Risk/Exit- plus Kommerz-Gate-Module in shared_py (wie CI, cwd shared/python).

Lokal:   python tools/production_selfcheck.py
DB:      modul_mate_selfcheck prueft M604 (app.tenant_modul_mate_gates) inkl.
         product_policy, wenn DATABASE_URL gesetzt ist. Ohne gesetztes DATABASE_URL
         im Profil production|staging|shadow, PRODUCTION=true oder
         SELFCHECK_DATABASE_REQUIRED=1 → Exit 1 (kein stilles SKIP).

Optional (CI-aehnlicher Repo-Scan, kann auf grossen Trees langsam sein):
  PRODUCTION_SELFCHECK_REPO_SCAN=1  bzw. unter PowerShell:
  $env:PRODUCTION_SELFCHECK_REPO_SCAN='1'

Exit-Codes:
  0 — Alle Subschritte erfolgreich. modul_mate_selfcheck: DB-SKIP ist nur im lokalen
      Dev-Profil ohne PRODUCTION/APP_ENV production|staging|shadow/SELFCHECK_DATABASE
      zulässig; in prod-ähnlichen Profilen fehlendes DATABASE_URL → 1.
  != 0 — Rückgabewert des ersten fehlgeschlagenen Subprozesses (welcher Schritt, steht
      als „FAIL: …“ direkt davor).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_CI_PLACEHOLDER_FILL = "ci_repeatable_secret_min_32_chars_x"

_SELFCHECK_RUFF_PATHS = (
    "tools/db_production_hardening.py",
    "tools/live_app_schema_fingerprint.py",
    "tools/modul_mate_selfcheck.py",
    "tools/production_selfcheck.py",
    "tools/refresh_migrations_schema_hash.py",
    "tools/refresh_schema_master_hash.py",
    "tools/validate_env_profile.py",
    "tests/unit/tools/test_selfcheck_cli_contract.py",
    "tests/unit/shared_py/test_modul_mate_db_gates.py",
    "tests/unit/shared_py/test_product_policy.py",
    "tests/unit/live_broker/test_modul_mate_order_gates.py",
    "tests/shared/test_model_layer_contract.py",
)

_SELFCHECK_BLACK_PATHS = (
    "tools/modul_mate_selfcheck.py",
    "tools/production_selfcheck.py",
    "tests/shared/test_model_layer_contract.py",
)

_MYPY_SHARED_TARGETS = (
    "src/shared_py/leverage_allocator.py",
    "src/shared_py/risk_engine.py",
    "src/shared_py/exit_engine.py",
    "src/shared_py/shadow_live_divergence.py",
    "src/shared_py/product_policy.py",
    "src/shared_py/modul_mate_db_gates.py",
    "src/shared_py/model_layer_contract.py",
)


def _prod_like_requires_database_url() -> bool:
    """Gleiche Logik wie modul_mate_selfcheck: DB in prod nicht optional."""
    s = (os.environ.get("SELFCHECK_DATABASE_REQUIRED") or "").strip()
    if s in ("1", "true", "yes", "on"):
        return True
    s = (os.environ.get("PRODUCTION") or "").strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    app = (os.environ.get("APP_ENV") or "development").strip().lower()
    return app in ("production", "staging", "shadow")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    mm = root / "tools" / "modul_mate_selfcheck.py"
    print(
        "==> modul_mate_selfcheck (M604 app.tenant_modul_mate_gates, "
        "profilbasiert DB-Pflicht)",
        flush=True,
    )
    r0 = subprocess.run([sys.executable, str(mm)], cwd=root)
    if r0.returncode != 0:
        print("FAIL: modul_mate_selfcheck", flush=True)
        return r0.returncode

    app_env_l = (os.environ.get("APP_ENV") or "").strip().lower()
    if app_env_l == "production":
        dsn = (os.environ.get("DATABASE_URL") or "").strip()
        if not dsn:
            print(
                "FAIL: APP_ENV=production: DATABASE_URL PFLICHT fuer "
                "DB-Ping/Schema-Hash-Check (Prompt 35) — kein stilles Ueberspringen.",
                flush=True,
            )
            return 1
        print(
            "==> db_production_hardening (APP_ENV=production, "
            "DB-Ping + MIGRATIONS/LIVE_APP_HASH Pflicht, Prompt 23+35)",
            flush=True,
        )
        r_prod = subprocess.run(
            [sys.executable, str(root / "tools" / "db_production_hardening.py")],
            cwd=root,
            env=os.environ.copy(),
        )
        if r_prod.returncode != 0:
            print(
                "FAIL: db_production_hardening under APP_ENV=production (Schema-Hash, "
                "LIVE_APP_SCHEMA, Seeds; siehe config/schema_master.hash)",
                flush=True,
            )
            return r_prod.returncode
    elif _prod_like_requires_database_url():
        print(
            "==> db_production_hardening (Schema-Hash, Seed-Lock; "
            "prod-aehnliches Profil)",
            flush=True,
        )
        r_h = subprocess.run(
            [sys.executable, str(root / "tools" / "db_production_hardening.py")],
            cwd=root,
            env=os.environ.copy(),
        )
        if r_h.returncode != 0:
            print(
                "FAIL: db_production_hardening (Schema-Drift oder "
                "Test-Platzhalter/Seeds in DB; siehe config/schema_master.hash)",
                flush=True,
            )
            return r_h.returncode

    print("==> ruff check (Selfcheck-Pfade)", flush=True)
    ruff_argv = [sys.executable, "-m", "ruff", "check", *(_SELFCHECK_RUFF_PATHS)]
    r_ruff = subprocess.run(ruff_argv, cwd=root)
    if r_ruff.returncode != 0:
        print(
            "FAIL: ruff check (Selfcheck-Dateien; "
            "pip install -r requirements-dev.txt)",
            flush=True,
        )
        return r_ruff.returncode

    print("==> black --check (Selfcheck-Tools + tests/shared)", flush=True)
    black_argv = [
        sys.executable,
        "-m",
        "black",
        "--check",
        *(_SELFCHECK_BLACK_PATHS),
    ]
    r_black = subprocess.run(black_argv, cwd=root)
    if r_black.returncode != 0:
        print(
            "FAIL: black --check (Selfcheck-Tools + tests/shared; "
            "pip install -r requirements-dev.txt)",
            flush=True,
        )
        return r_black.returncode

    print(
        "==> mypy (kritische shared_py-Module, cwd shared/python)",
        flush=True,
    )
    shared_pkg = root / "shared" / "python"
    r_mypy = subprocess.run(
        [sys.executable, "-m", "mypy", *(_MYPY_SHARED_TARGETS)],
        cwd=shared_pkg,
    )
    if r_mypy.returncode != 0:
        print(
            "FAIL: mypy (kritische shared_py-Module; "
            "pip install -r requirements-dev.txt)",
            flush=True,
        )
        return r_mypy.returncode

    print(
        "==> pytest (Modul Mate / product_policy / live-broker / model_layer)",
        flush=True,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "shared" / "python" / "src")
    r1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/shared_py/test_modul_mate_db_gates.py",
            "tests/unit/shared_py/test_product_policy.py",
            "tests/unit/live_broker/test_modul_mate_order_gates.py",
            "tests/shared/test_model_layer_contract.py",
            "-q",
            "--tb=short",
        ],
        cwd=root,
        env=env,
    )
    if r1.returncode != 0:
        print(
            "FAIL: pytest (Modul Mate / product_policy / live-broker / model_layer)",
            flush=True,
        )
        return r1.returncode

    print("==> pytest tests/llm_eval", flush=True)
    r_eval = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/llm_eval", "-q", "--tb=short"],
        cwd=root,
        env=env,
    )
    if r_eval.returncode != 0:
        print(
            "FAIL: pytest tests/llm_eval (Prompt-Governance / Guardrails-Regression)",
            flush=True,
        )
        return r_eval.returncode

    print("==> check_contracts.py", flush=True)
    r2 = subprocess.run(
        [sys.executable, str(root / "tools" / "check_contracts.py")],
        cwd=root,
    )
    if r2.returncode != 0:
        print(
            "FAIL: check_contracts (TS/Python/OpenAPI-Konsistenz)",
            flush=True,
        )
        return r2.returncode

    print("==> check_schema.py (signals_fixture)", flush=True)
    r3 = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "check_schema.py"),
            "--schema",
            str(
                root
                / "infra"
                / "tests"
                / "schemas"
                / "signals_recent_response.schema.json"
            ),
            "--json_file",
            str(root / "tests" / "fixtures" / "signals_fixture.json"),
        ],
        cwd=root,
    )
    if r3.returncode != 0:
        print("FAIL: check_schema (signals_fixture vs. Schema)", flush=True)
        return r3.returncode

    print("==> check_production_env_template_security.py", flush=True)
    r4 = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "check_production_env_template_security.py"),
        ],
        cwd=root,
    )
    if r4.returncode != 0:
        print(
            "FAIL: check_production_env_template_security (.env.*.example)",
            flush=True,
        )
        return r4.returncode

    ex_local = root / ".env.local.example"
    print(
        "==> validate_env_profile (optional, aus .env.local.example)",
        flush=True,
    )
    if ex_local.is_file():
        body = ex_local.read_text(encoding="utf-8").replace(
            "<SET_ME>", _CI_PLACEHOLDER_FILL
        )
        fd, tmp_name = tempfile.mkstemp(
            suffix=".env.local",
            prefix="production_selfcheck_",
        )
        tmp_path = Path(tmp_name)
        try:
            os.close(fd)
            tmp_path.write_text(body, encoding="utf-8")
            r_env = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "validate_env_profile.py"),
                    "--env-file",
                    str(tmp_path),
                    "--profile",
                    "local",
                ],
                cwd=root,
            )
            if r_env.returncode != 0:
                print(
                    "FAIL: validate_env_profile "
                    "(synthetisch aus .env.local.example, wie CI)",
                    flush=True,
                )
                return r_env.returncode
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        print(
            "SKIP: .env.local.example fehlt (validate_env_profile)",
            flush=True,
        )

    scan = os.environ.get("PRODUCTION_SELFCHECK_REPO_SCAN", "").strip().lower()
    if scan in ("1", "true", "yes", "on"):
        print(
            "==> release_sanity_checks.py (PRODUCTION_SELFCHECK_REPO_SCAN)",
            flush=True,
        )
        r5 = subprocess.run(
            [sys.executable, str(root / "tools" / "release_sanity_checks.py")],
            cwd=root,
        )
        if r5.returncode != 0:
            print("FAIL: release_sanity_checks", flush=True)
            return r5.returncode

    tail = (
        "ruff + black + mypy + pytest + llm_eval + "
        "contracts + schema + env-template-security"
    )
    if ex_local.is_file():
        tail += " + env.local.example profile"
    if scan in ("1", "true", "yes", "on"):
        tail += " + release_sanity"
    print(f"OK: production_selfcheck abgeschlossen ({tail})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
