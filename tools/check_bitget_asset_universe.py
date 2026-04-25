#!/usr/bin/env python3
"""Static checks for Bitget multi-asset universe governance."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "bitget_asset_universe.md"
CONTRACT_DOC_PATH = ROOT / "docs" / "production_10_10" / "instrument_catalog_contract.md"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
MATRIX_PATH = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
REFRESH_SCRIPT_PATH = ROOT / "scripts" / "refresh_bitget_asset_universe.py"
ASSET_UNIVERSE_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "asset_universe.py"
INSTRUMENT_PATHS = (
    ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "instruments.py",
    ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "catalog.py",
    ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "metadata.py",
    ASSET_UNIVERSE_PATH,
)
TEST_PATHS = (
    ROOT / "tests" / "tools" / "test_check_bitget_asset_universe.py",
    ROOT / "tests" / "security" / "test_bitget_asset_universe_contracts.py",
    ROOT / "tests" / "shared" / "test_bitget_asset_universe.py",
)
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "bitget_asset_universe_sample.json"

BTC_ONLY_PHRASES = (
    "btc-only",
    "nur btc",
    "ausschliesslich btc",
    "ausschließlich btc",
    "only btc",
    "default btcusdt",
)
AUTO_LIVE_PHRASES = (
    "alle assets automatisch live",
    "all assets automatically live",
    "automatisch livefaehig",
    "automatisch livefähig",
    "jede discovery sofort live",
)
REQUIRED_DOC_TERMS = (
    "quarant",
    "delist",
    "susp",
)
CONSOLE_DOC_TERMS = ("asset-universum", "asset universum")
NO_GO_PRIMARY_TERM = "asset-freigabe"
NO_GO_SECONDARY_TERMS = ("kein live", "kein echtgeld-live", "block")


@dataclass(frozen=True)
class UniverseIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _issue(
    issues: list[UniverseIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    issues.append(
        UniverseIssue(
            severity=severity,
            code=code,
            message=message,
            path=str(path) if path is not None else None,
        )
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def analyze_asset_universe(
    *,
    doc_path: Path = DOC_PATH,
    contract_doc_path: Path = CONTRACT_DOC_PATH,
    main_console_doc_path: Path = MAIN_CONSOLE_DOC_PATH,
    no_go_doc_path: Path = NO_GO_DOC_PATH,
    matrix_path: Path = MATRIX_PATH,
    refresh_script_path: Path = REFRESH_SCRIPT_PATH,
    fixture_path: Path = FIXTURE_PATH,
    instrument_paths: tuple[Path, ...] = INSTRUMENT_PATHS,
    test_paths: tuple[Path, ...] = TEST_PATHS,
) -> dict[str, Any]:
    issues: list[UniverseIssue] = []
    doc_text = ""

    if not doc_path.is_file():
        _issue(
            issues,
            severity="error",
            code="asset_universe_doc_missing",
            message="Missing bitget asset universe documentation.",
            path=doc_path,
        )
    else:
        doc_text = doc_path.read_text(encoding="utf-8").lower()
    if not contract_doc_path.is_file():
        _issue(
            issues,
            severity="error",
            code="instrument_contract_doc_missing",
            message="Missing instrument catalog contract documentation.",
            path=contract_doc_path,
        )
    if not refresh_script_path.is_file():
        _issue(
            issues,
            severity="error",
            code="refresh_script_missing",
            message="Missing scripts/refresh_bitget_asset_universe.py.",
            path=refresh_script_path,
        )
    if not fixture_path.is_file():
        _issue(
            issues,
            severity="warning",
            code="fixture_missing",
            message="Fixture tests/fixtures/bitget_asset_universe_sample.json missing.",
            path=fixture_path,
        )

    missing_instrument_files = [str(path) for path in instrument_paths if not path.is_file()]
    for missing_path in missing_instrument_files:
        _issue(
            issues,
            severity="error",
            code="instrument_file_missing",
            message="Required instrument/catalog/metadata file missing.",
            path=Path(missing_path),
        )

    missing_tests = [str(path) for path in test_paths if not path.is_file()]
    for missing_path in missing_tests:
        _issue(
            issues,
            severity="error",
            code="required_test_missing",
            message="Required asset-universe test file missing.",
            path=Path(missing_path),
        )

    if doc_text:
        for phrase in BTC_ONLY_PHRASES:
            if phrase in doc_text:
                _issue(
                    issues,
                    severity="error",
                    code="btc_only_assumption_detected",
                    message=f"BTC-only wording detected: {phrase}",
                    path=doc_path,
                )
        for phrase in AUTO_LIVE_PHRASES:
            if phrase in doc_text:
                negated = re.search(rf"(nicht|kein)\s+[^.\n]{{0,24}}{re.escape(phrase)}", doc_text)
                if negated:
                    continue
                _issue(
                    issues,
                    severity="error",
                    code="auto_live_claim_detected",
                    message=f"Unsafe automatic-live wording detected: {phrase}",
                    path=doc_path,
                )
        for marker in REQUIRED_DOC_TERMS:
            if marker not in doc_text:
                _issue(
                    issues,
                    severity="error",
                    code="required_governance_term_missing",
                    message=f"Required governance topic not documented: {marker}",
                    path=doc_path,
                )
    if main_console_doc_path.is_file():
        main_console_text = main_console_doc_path.read_text(encoding="utf-8").lower()
        if not any(term in main_console_text for term in CONSOLE_DOC_TERMS):
            _issue(
                issues,
                severity="error",
                code="main_console_asset_universe_missing",
                message="Main-Console-Doku erwaehnt Asset-Universum nicht.",
                path=main_console_doc_path,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="main_console_doc_missing",
            message="Missing main_console_product_direction.md.",
            path=main_console_doc_path,
        )

    if no_go_doc_path.is_file():
        no_go_text = no_go_doc_path.read_text(encoding="utf-8").lower()
        has_primary = NO_GO_PRIMARY_TERM in no_go_text
        has_secondary = any(term in no_go_text for term in NO_GO_SECONDARY_TERMS)
        if not (has_primary and has_secondary):
            _issue(
                issues,
                severity="error",
                code="no_go_asset_release_missing",
                message="No-Go-Regeln erwaehnen fehlende Asset-Freigabe nicht ausreichend.",
                path=no_go_doc_path,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="no_go_doc_missing",
            message="Missing no_go_rules.md.",
            path=no_go_doc_path,
        )

    unsafe_live_code_paths = [
        ROOT / "shared" / "python" / "src" / "shared_py" / "bitget",
        ROOT / "services",
    ]
    for base_path in unsafe_live_code_paths:
        if not base_path.exists():
            continue
        for path in base_path.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "live_allowed = true" in text or '"live_allowed": true' in text:
                _issue(
                    issues,
                    severity="error",
                    code="unsafe_live_default_true",
                    message="Codepfad mit pauschalem live_allowed=true gefunden.",
                    path=path,
                )

    matrix_present = matrix_path.is_file()
    matrix_has_category = False
    if matrix_present:
        matrix = _load_yaml(matrix_path)
        categories = matrix.get("categories")
        if isinstance(categories, list):
            matrix_has_category = any(
                isinstance(item, dict) and str(item.get("id")) == "bitget_asset_universe"
                for item in categories
            )
        if not matrix_has_category:
            _issue(
                issues,
                severity="warning",
                code="matrix_category_missing",
                message="evidence_matrix.yaml exists but has no bitget_asset_universe category.",
                path=matrix_path,
            )

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "doc_exists": doc_path.is_file(),
        "contract_doc_exists": contract_doc_path.is_file(),
        "refresh_script_exists": refresh_script_path.is_file(),
        "fixture_exists": fixture_path.is_file(),
        "matrix_present": matrix_present,
        "matrix_has_bitget_asset_universe": matrix_has_category,
        "missing_instrument_files": missing_instrument_files,
        "missing_test_files": missing_tests,
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_bitget_asset_universe: governance surface",
        f"ok={str(summary['ok']).lower()} doc_exists={summary['doc_exists']}",
        f"contract_doc_exists={summary['contract_doc_exists']} refresh_script_exists={summary['refresh_script_exists']}",
        f"fixture_exists={summary['fixture_exists']}",
        "matrix_present="
        + str(summary["matrix_present"]).lower()
        + " matrix_has_bitget_asset_universe="
        + str(summary["matrix_has_bitget_asset_universe"]).lower(),
        f"missing_instrument_files={len(summary['missing_instrument_files'])}",
        f"missing_test_files={len(summary['missing_test_files'])}",
    ]
    for issue in summary["issues"]:
        suffix = f" [{issue['path']}]" if issue.get("path") else ""
        lines.append(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{suffix}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = analyze_asset_universe()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_text(summary))

    if summary["error_count"] > 0:
        return 1
    if args.strict and summary["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
