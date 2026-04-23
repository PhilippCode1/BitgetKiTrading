#!/usr/bin/env python3
"""
Release-/Merge-Gates: Ballast, offensichtliche Secrets, riskante Port-Binds.

Kein Ersatz fuer Secret-Scanner in der Produktion (z.B. Gitleaks).

Aufruf vom Repo-Root:
  python tools/release_sanity_checks.py
  python tools/release_sanity_checks.py --strict   # zusaetzlich WARN -> Exit 1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "build-cursor",
    "dist",
    "htmlcov",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "artifacts",
    "grafanadata",
    "prometheusdata",
}

# Tracked-Quellen (keine Lockfiles / Coverage JSON)
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".sh", ".env", ".example", ".md", ".toml"}
MAX_SOURCE_BYTES = 12 * 1024 * 1024  # 12 MiB — Build-Ballast

SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk_live_[0-9a-zA-Z]{20,}"), "Stripe live key"),
    (re.compile(r"sk-(?:proj|test|live)-[A-Za-z0-9_\-]{20,}"), "OpenAI-style API key"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "Slack token"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "PEM private key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
]

# Nur offensichtliche Wildcard-Host-Publishes (ohne Umgebungsvariable)
RAW_WILDCARD_PORT = re.compile(r"^\s*-\s*[\"']?0\.0\.0\.0:\d+:\d+")


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.name in {"coverage.json", ".coverage", "pnpm-lock.yaml"}:
            continue
        out.append(p)
    return out


def _check_file_size(path: Path) -> tuple[str, str] | None:
    if path.suffix.lower() not in TEXT_SUFFIXES | {".lock", ".svg", ".png", ".jpg"}:
        return None
    if path.suffix.lower() in {".png", ".jpg", ".svg"}:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    if st.st_size > MAX_SOURCE_BYTES:
        return ("ERROR", f"Datei > {MAX_SOURCE_BYTES // (1024 * 1024)} MiB: {path}")
    return None


def _check_secrets(rel: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    lower = rel.as_posix().lower()
    if "node_modules" in lower or ".example" in rel.name or rel.name == ".env.example":
        return issues
    for pat, label in SECRET_PATTERNS:
        if pat.search(text):
            issues.append(("ERROR", f"{label}-aehnliches Muster in {rel}"))
    return issues


def _check_compose_ports(path: Path, lines: list[str]) -> list[tuple[str, str]]:
    """`docker-compose.yml` ohne Overlay sollte keine nackten 0.0.0.0-Binds haben."""
    issues: list[tuple[str, str]] = []
    if path.name != "docker-compose.yml":
        return issues
    for i, line in enumerate(lines, 1):
        if RAW_WILDCARD_PORT.search(line):
            issues.append(
                (
                    "WARN",
                    f"{path}:{i} — 0.0.0.0 Host-Publish; bevorzugt 127.0.0.1 oder COMPOSE_*_BIND",
                )
            )
    return issues


def _check_requirements_pins(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if path.name != "requirements-dev.txt":
        return issues
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-r "):
            continue
        if "@" in s and "://" in s:
            continue
        if "==" in s:
            continue
        if s.endswith("\\"):
            continue
        issues.append(
            (
                "WARN",
                f"{path}:{i} — Paket ohne ==-Pin: {s[:80]}",
            )
        )
    return issues


def _check_runtime_constraints_pins(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if path.name != "constraints-runtime.txt":
        return issues
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "==" not in s:
            issues.append(("ERROR", f"{path}:{i} — Runtime-Constraint ohne exakten ==-Pin: {s[:80]}"))
    return issues


def _check_dashboard_package_scripts(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    rel = path.relative_to(ROOT).as_posix()
    if rel != "apps/dashboard/package.json":
        return issues
    if "--passWithNoTests" in text:
        issues.append(("ERROR", f"{path} — Dashboard-Testscript darf kein --passWithNoTests verwenden"))
    if '"start"' in text and "next start" in text:
        issues.append(("WARN", f"{path} — Standalone-Build sollte nicht ueber next start gestartet werden"))
    return issues


def _check_dashboard_next_config(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    rel = path.relative_to(ROOT).as_posix()
    if rel != "apps/dashboard/next.config.js":
        return issues
    if 'output: "standalone"' not in text:
        issues.append(("ERROR", f"{path} — Dashboard-Next-Konfig ohne output: standalone"))
    if 'distDir: "build"' not in text:
        issues.append(("WARN", f"{path} — Dashboard-Build sollte distDir=build fuer artefaktarmen Release-Pfad setzen"))
    return issues


def _check_dashboard_dockerfile(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    rel = path.relative_to(ROOT).as_posix()
    if rel != "apps/dashboard/Dockerfile":
        return issues
    if "COPY --from=builder --chown=nextjs:nodejs /app/node_modules" in text:
        issues.append(("ERROR", f"{path} — Runner kopiert Workspace-node_modules statt Standalone-Artefakt"))
    if "CMD [\"pnpm\", \"start\"]" in text or "next start" in text:
        issues.append(("ERROR", f"{path} — Produktionsrunner darf nicht ueber pnpm/next start laufen"))
    if "build/standalone" not in text:
        issues.append(("WARN", f"{path} — Dashboard-Runner sollte explizit Standalone-Ausgabe kopieren"))
    return issues


def _check_python_dockerfile_constraints(path: Path, text: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if path.parent.parent.name != "services" or path.name != "Dockerfile":
        return issues
    if "FROM python:" not in text:
        return issues
    if "constraints-runtime.txt" not in text:
        issues.append(("ERROR", f"{path} — Python-Service-Dockerfile ohne constraints-runtime.txt"))
    if "USER appuser" not in text:
        issues.append(("WARN", f"{path} — Python-Service-Dockerfile sollte non-root laufen"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Release-Sanity-Checks")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="WARN ebenfalls als Fehler werten (Release-Candidate/Production)",
    )
    args = parser.parse_args()

    errors = 0
    warns = 0

    for path in _iter_files():
        rel = path.relative_to(ROOT)
        if hit := _check_file_size(path):
            sev, msg = hit
            print(msg, file=sys.stderr)
            errors += 1

        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = raw.splitlines()
        for sev, msg in _check_compose_ports(path, lines):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_requirements_pins(path, raw):
            print(msg, file=sys.stdout)
            warns += 1

        for sev, msg in _check_runtime_constraints_pins(path, raw):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_dashboard_package_scripts(path, raw):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_dashboard_next_config(path, raw):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_dashboard_dockerfile(path, raw):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_python_dockerfile_constraints(path, raw):
            print(msg, file=sys.stderr if sev == "ERROR" else sys.stdout)
            if sev == "ERROR":
                errors += 1
            else:
                warns += 1

        for sev, msg in _check_secrets(rel, raw):
            print(msg, file=sys.stderr)
            errors += 1

    if args.strict and warns > 0:
        print(f"release_sanity_checks: strict — {warns} Warnung(en) als Fehler", file=sys.stderr)
        return 1

    if errors > 0:
        print(f"release_sanity_checks: {errors} Fehler", file=sys.stderr)
        return 1

    print(f"release_sanity_checks: ok (warns={warns})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
