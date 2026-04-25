from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from tools.check_bitget_asset_universe import analyze_asset_universe


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_bitget_asset_universe.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path, tuple[Path, ...], tuple[Path, ...]]:
    doc = tmp_path / "docs" / "production_10_10" / "bitget_asset_universe.md"
    contract_doc = tmp_path / "docs" / "production_10_10" / "instrument_catalog_contract.md"
    main_console_doc = tmp_path / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go_doc = tmp_path / "docs" / "production_10_10" / "no_go_rules.md"
    matrix = tmp_path / "docs" / "production_10_10" / "evidence_matrix.yaml"
    refresh_script = tmp_path / "scripts" / "refresh_bitget_asset_universe.py"
    fixture_json = tmp_path / "tests" / "fixtures" / "bitget_asset_universe_sample.json"
    instrument_paths = (
        tmp_path / "shared/python/src/shared_py/bitget/instruments.py",
        tmp_path / "shared/python/src/shared_py/bitget/catalog.py",
        tmp_path / "shared/python/src/shared_py/bitget/metadata.py",
        tmp_path / "shared/python/src/shared_py/bitget/asset_universe.py",
    )
    test_paths = (
        tmp_path / "tests/tools/test_check_bitget_asset_universe.py",
        tmp_path / "tests/security/test_bitget_asset_universe_contracts.py",
        tmp_path / "tests/shared/test_bitget_asset_universe.py",
    )
    _write(
        doc,
        (
            "# Bitget Asset Universe\n\n"
            "Quarantaene und Delisting/Suspension sind harte Live-Blocker.\n"
            "Assets brauchen explizite Live-Freigabe mit Gates.\n"
        ),
    )
    _write(
        matrix,
        yaml.safe_dump({"categories": [{"id": "bitget_asset_universe"}]}, sort_keys=False),
    )
    _write(contract_doc, "# Contract\n")
    _write(main_console_doc, "# Main Console\nAsset-Universum ist sichtbar.\n")
    _write(no_go_doc, "# No-Go\nOhne Asset-Freigabe kein Live-Block.\n")
    _write(refresh_script, "#!/usr/bin/env python3\n")
    _write(fixture_json, "{\"assets\": []}\n")
    for path in instrument_paths + test_paths:
        _write(path, "# fixture\n")
    return (
        doc,
        contract_doc,
        main_console_doc,
        no_go_doc,
        matrix,
        refresh_script,
        fixture_json,
        instrument_paths,
        test_paths,
    )


def test_analyze_asset_universe_ok_fixture(tmp_path: Path) -> None:
    (
        doc,
        contract_doc,
        main_console_doc,
        no_go_doc,
        matrix,
        refresh_script,
        fixture_json,
        instrument_paths,
        test_paths,
    ) = _build_fixture(tmp_path)
    summary = analyze_asset_universe(
        doc_path=doc,
        contract_doc_path=contract_doc,
        main_console_doc_path=main_console_doc,
        no_go_doc_path=no_go_doc,
        matrix_path=matrix,
        refresh_script_path=refresh_script,
        fixture_path=fixture_json,
        instrument_paths=instrument_paths,
        test_paths=test_paths,
    )
    assert summary["error_count"] == 0
    assert summary["matrix_has_bitget_asset_universe"] is True


def test_detects_btc_only_and_auto_live_claims(tmp_path: Path) -> None:
    (
        doc,
        contract_doc,
        main_console_doc,
        no_go_doc,
        matrix,
        refresh_script,
        fixture_json,
        instrument_paths,
        test_paths,
    ) = _build_fixture(tmp_path)
    _write(
        doc,
        (
            "# Scope\n"
            "Dies ist BTC-only und alle assets automatisch live.\n"
            "Quarantaene Delisting Suspension.\n"
        ),
    )
    summary = analyze_asset_universe(
        doc_path=doc,
        contract_doc_path=contract_doc,
        main_console_doc_path=main_console_doc,
        no_go_doc_path=no_go_doc,
        matrix_path=matrix,
        refresh_script_path=refresh_script,
        fixture_path=fixture_json,
        instrument_paths=instrument_paths,
        test_paths=test_paths,
    )
    codes = {issue["code"] for issue in summary["issues"]}
    assert "btc_only_assumption_detected" in codes
    assert "auto_live_claim_detected" in codes


def test_detects_missing_quarantine_delisting_terms(tmp_path: Path) -> None:
    (
        doc,
        contract_doc,
        main_console_doc,
        no_go_doc,
        matrix,
        refresh_script,
        fixture_json,
        instrument_paths,
        test_paths,
    ) = _build_fixture(tmp_path)
    _write(doc, "# Scope\nKeine Governance-Begriffe.\n")
    summary = analyze_asset_universe(
        doc_path=doc,
        contract_doc_path=contract_doc,
        main_console_doc_path=main_console_doc,
        no_go_doc_path=no_go_doc,
        matrix_path=matrix,
        refresh_script_path=refresh_script,
        fixture_path=fixture_json,
        instrument_paths=instrument_paths,
        test_paths=test_paths,
    )
    assert any(issue["code"] == "required_governance_term_missing" for issue in summary["issues"])


def test_warns_when_matrix_category_missing(tmp_path: Path) -> None:
    (
        doc,
        contract_doc,
        main_console_doc,
        no_go_doc,
        matrix,
        refresh_script,
        fixture_json,
        instrument_paths,
        test_paths,
    ) = _build_fixture(tmp_path)
    _write(matrix, yaml.safe_dump({"categories": [{"id": "other"}]}, sort_keys=False))
    summary = analyze_asset_universe(
        doc_path=doc,
        contract_doc_path=contract_doc,
        main_console_doc_path=main_console_doc,
        no_go_doc_path=no_go_doc,
        matrix_path=matrix,
        refresh_script_path=refresh_script,
        fixture_path=fixture_json,
        instrument_paths=instrument_paths,
        test_paths=test_paths,
    )
    assert any(issue["code"] == "matrix_category_missing" for issue in summary["issues"])


def test_json_output_is_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(completed.stdout)
    assert "error_count" in parsed
    assert "issues" in parsed
    assert "refresh_script_exists" in parsed
