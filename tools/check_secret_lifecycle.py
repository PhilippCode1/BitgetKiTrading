#!/usr/bin/env python3
"""Static checker for secret lifecycle and rotation readiness."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk_live_[0-9a-zA-Z]{20,}"),
    re.compile(r"sk-(?:proj|test|live)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


@dataclass(frozen=True)
class CheckResult:
    id: str
    ok: bool
    severity: str
    message: str
    path: str | None = None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


def _contains(rel: str, *needles: str) -> bool:
    text = _read(ROOT / rel).lower()
    return all(needle.lower() in text for needle in needles)


def _has_secret_pattern(rel: str) -> bool:
    text = _read(ROOT / rel)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    global ROOT
    old_root = ROOT
    ROOT = root
    try:
        results: list[CheckResult] = []
        required_files = {
            "rotation_doc": "docs/production_10_10/secrets_rotation_and_credential_hygiene.md",
            "report_template": "docs/production_10_10/secrets_rotation_report_template.md",
            "drill_script": "scripts/secrets_rotation_drill.py",
            "policy_module": "shared/python/src/shared_py/secret_lifecycle.py",
            "drill_tests": "tests/scripts/test_secrets_rotation_drill.py",
            "policy_tests": "tests/security/test_secret_lifecycle_policy.py",
            "checker_tests": "tests/tools/test_check_secret_lifecycle.py",
        }
        for check_id, rel in required_files.items():
            results.append(
                CheckResult(
                    id=check_id,
                    ok=_exists(rel),
                    severity="P1",
                    message=f"Required file exists: {rel}",
                    path=rel,
                )
            )

        matrix_yaml = ROOT / "docs/production_10_10/evidence_matrix.yaml"
        matrix_md = ROOT / "docs/production_10_10/evidence_matrix.md"
        matrix_ok = False
        if matrix_yaml.is_file():
            matrix_ok = "secrets_management" in _read(matrix_yaml)
        if matrix_md.is_file():
            matrix_ok = matrix_ok or "secrets_management" in _read(matrix_md)
        results.append(
            CheckResult(
                id="evidence_matrix_secrets_management",
                ok=matrix_ok,
                severity="P1",
                message="Evidence matrix references secrets_management.",
                path="docs/production_10_10/evidence_matrix.*",
            )
        )

        results.append(
            CheckResult(
                id="no_go_secret_rotation",
                ok=_contains(
                    "docs/production_10_10/no_go_rules.md",
                    "Secret Rotation",
                ),
                severity="P0",
                message="No-Go rules mention Secret Rotation.",
                path="docs/production_10_10/no_go_rules.md",
            )
        )
        results.append(
            CheckResult(
                id="env_doc_secret_store_rotation",
                ok=_contains("docs/SECRETS_MATRIX.md", "rotation")
                and (
                    _contains("docs/SECRETS_MATRIX.md", "secret-store")
                    or _contains("docs/SECRETS_MATRIX.md", "Vault")
                    or _contains("docs/SECRETS_MATRIX.md", "KMS")
                ),
                severity="P1",
                message="ENV/Secrets documentation references secret store and rotation.",
                path="docs/SECRETS_MATRIX.md",
            )
        )

        docs_to_scan = [
            "docs/production_10_10/secrets_rotation_and_credential_hygiene.md",
            "docs/production_10_10/secrets_rotation_report_template.md",
        ]
        for rel in docs_to_scan:
            results.append(
                CheckResult(
                    id=f"no_raw_secret_pattern:{rel}",
                    ok=not _has_secret_pattern(rel),
                    severity="P0",
                    message=f"No obvious raw secret pattern in {rel}.",
                    path=rel,
                )
            )
        return results
    finally:
        ROOT = old_root


def build_summary(results: list[CheckResult]) -> dict[str, Any]:
    failed = [r for r in results if not r.ok]
    return {
        "ok": not failed,
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failures": [asdict(r) for r in failed],
        "checks": [asdict(r) for r in results],
    }


def print_text(summary: dict[str, Any]) -> None:
    print("secret_lifecycle_check")
    print(f"ok={str(summary['ok']).lower()}")
    print(f"passed={summary['passed']} failed={summary['failed']} total={summary['total']}")
    for failure in summary["failures"]:
        path = f" path={failure['path']}" if failure.get("path") else ""
        print(
            f"FAIL [{failure['severity']}] {failure['id']}: "
            f"{failure['message']}{path}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any failed check.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_checks()
    summary = build_summary(results)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_text(summary)
    if args.strict and not summary["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
