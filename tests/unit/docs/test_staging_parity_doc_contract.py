"""Maschinenpruefbarer Vertrag: Staging-Paritaets-Dokus verweisen auf existierende Artefakte."""

from __future__ import annotations

from pathlib import Path

from config.bootstrap_env_checks import bootstrap_env_consistency_issues

ROOT = Path(__file__).resolve().parents[3]

# docs/STAGING_PARITY.md — Validierung / Siehe auch (keine .env-Dateien im Git).
DOCS_STAGING_PARITY_PATHS: tuple[str, ...] = (
    "docs/STAGING_PARITY.md",
    "tools/validate_env_profile.py",
    "config/bootstrap_env_checks.py",
    "config/bootstrap_env_truth.py",
    "apps/dashboard/src/lib/server-env.ts",
    "docs/env_profiles.md",
    "docs/CONFIGURATION.md",
)

# STAGING_PARITY.md (Repo-Root) — Verifikation / Weitere Werkzeuge / Siehe auch.
ROOT_STAGING_PARITY_PATHS: tuple[str, ...] = (
    "STAGING_PARITY.md",
    "config/settings.py",
    "apps/dashboard/src/lib/server-env.ts",
    "apps/dashboard/next.config.js",
    "tools/validate_env_profile.py",
    "scripts/staging_smoke.py",
    "scripts/api_integration_smoke.py",
    "scripts/verify_ai_operator_explain.py",
    "docs/SECRETS_MATRIX.md",
    "config/required_secrets_matrix.json",
    "docs/env_profiles.md",
    "docs/operator_urls_and_secrets.md",
    "AI_FLOW.md",
)


def test_docs_staging_parity_exists() -> None:
    p = ROOT / "docs" / "STAGING_PARITY.md"
    assert p.is_file(), f"fehlt {p}"


def test_root_staging_parity_exists() -> None:
    p = ROOT / "STAGING_PARITY.md"
    assert p.is_file(), f"fehlt {p}"


def test_staging_parity_referenced_repo_files_exist() -> None:
    seen: set[str] = set()
    for rel in (*DOCS_STAGING_PARITY_PATHS, *ROOT_STAGING_PARITY_PATHS):
        if rel in seen:
            continue
        seen.add(rel)
        path = ROOT / rel
        assert path.is_file(), f"Staging-Paritaets-Doku verweist auf fehlende Datei: {rel}"


def test_bootstrap_env_consistency_issues_callable() -> None:
    """Dokumentierter Einstiegspunkt in STAGING_PARITY (Abschnitt Validierung)."""
    assert callable(bootstrap_env_consistency_issues)
    issues = bootstrap_env_consistency_issues({}, profile="local")
    assert isinstance(issues, list)
