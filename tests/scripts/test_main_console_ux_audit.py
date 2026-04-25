from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "main_console_ux_audit.py"


def test_ux_audit_dry_run_works() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry-run=true" in proc.stdout


def test_json_parseable_and_required_areas_present() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert "known_routes" in payload
    assert "required_area_presence" in payload
    assert "Sicherheitszentrale" in payload["required_area_presence"]
    assert "Asset-Universum" in payload["required_area_presence"]
    assert payload["required_area_presence"]["Sicherheitszentrale"] is True
    assert payload["required_area_presence"]["Asset-Universum"] is True


def test_billing_pricing_reste_and_unmapped_routes_detected() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert "billing_customer_pricing_saas_hits" in payload
    assert "routes_without_main_console_mapping" in payload
    assert isinstance(payload["billing_customer_pricing_saas_hits"], list)
    assert isinstance(payload["routes_without_main_console_mapping"], list)


def test_empty_and_error_state_checks_reported() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert "empty_state_guard_missing" in payload
    assert "error_state_guard_missing" in payload


def test_english_label_hits_field_present() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert "english_label_policy_hits" in payload


def test_report_contains_required_sections(tmp_path: Path) -> None:
    out = tmp_path / "ux.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = out.read_text(encoding="utf-8")
    assert "## Routeninventar" in text
    assert "## Empty-State Pflicht" in text
    assert "## Error-State Pflicht" in text
    assert "## Routenklassifikation" in text
