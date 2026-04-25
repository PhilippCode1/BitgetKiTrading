from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_german_only_ui import analyze_german_ui


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_german_only_ui.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    dashboard_src = tmp_path / "apps" / "dashboard" / "src"
    messages_dir = dashboard_src / "messages"
    policy = tmp_path / "docs" / "production_10_10" / "german_only_ui_policy.md"
    glossary = tmp_path / "docs" / "production_10_10" / "german_ui_glossary.md"

    _write(
        policy,
        "# Policy\n\n## 3) Verbindliches Glossar\nHauptkonsole Systemzustand Betreiber Echtgeldmodus Papiermodus Schattenmodus Not-Stopp Sicherheits-Sperre Abgleich Kein Handel Quarantäne Live-Blocker\n",
    )
    _write(
        glossary,
        "# Glossar\nHauptkonsole Systemzustand Betreiber Echtgeldmodus Papiermodus Schattenmodus Not-Stopp Sicherheits-Sperre Abgleich Kein Handel Quarantäne Live-Blocker\n",
    )
    _write(messages_dir / "de.json", '{"console":{"nav":{"health":"Systemzustand & Vorfälle"}}}')
    _write(messages_dir / "en.json", '{"console":{"nav":{"health":"Health & incidents"}}}')
    _write(dashboard_src / "components" / "X.tsx", 'export function X(){return <button>Speichern</button>}\n')
    return dashboard_src, messages_dir, policy, glossary


def test_english_visible_label_is_detected(tmp_path: Path) -> None:
    dashboard_src, messages_dir, policy, glossary = _fixture(tmp_path)
    _write(
        dashboard_src / "components" / "Bad.tsx",
        'export function Bad(){return <div>Health & Incidents</div>}\n',
    )
    summary = analyze_german_ui(
        dashboard_src=dashboard_src,
        messages_dir=messages_dir,
        policy_doc=policy,
        glossary_doc=glossary,
    )
    assert any(issue["code"] == "critical_english_visible_label" for issue in summary["issues"])


def test_technical_variable_not_flagged(tmp_path: Path) -> None:
    dashboard_src, messages_dir, policy, glossary = _fixture(tmp_path)
    _write(
        dashboard_src / "lib" / "tech.ts",
        'export const x = "NEXT_PUBLIC_API_BASE_URL";\n',
    )
    summary = analyze_german_ui(
        dashboard_src=dashboard_src,
        messages_dir=messages_dir,
        policy_doc=policy,
        glossary_doc=glossary,
    )
    assert not any(issue["code"] == "critical_english_visible_label" for issue in summary["issues"])


def test_billing_pricing_visible_text_detected(tmp_path: Path) -> None:
    dashboard_src, messages_dir, policy, glossary = _fixture(tmp_path)
    _write(
        dashboard_src / "components" / "Billing.tsx",
        'export function Billing(){return <div>Billing</div>}\n',
    )
    summary = analyze_german_ui(
        dashboard_src=dashboard_src,
        messages_dir=messages_dir,
        policy_doc=policy,
        glossary_doc=glossary,
    )
    assert any(issue["code"] == "out_of_scope_visible_phrase" for issue in summary["issues"])


def test_german_labels_are_accepted(tmp_path: Path) -> None:
    dashboard_src, messages_dir, policy, glossary = _fixture(tmp_path)
    _write(
        dashboard_src / "components" / "Good.tsx",
        'export function Good(){return <div>Systemzustand und Risiko</div>}\n',
    )
    summary = analyze_german_ui(
        dashboard_src=dashboard_src,
        messages_dir=messages_dir,
        policy_doc=policy,
        glossary_doc=glossary,
    )
    assert summary["error_count"] == 0


def test_json_output_is_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(completed.stdout)
    assert "files_scanned" in parsed
    assert "issues" in parsed


def test_strict_fails_correctly(tmp_path: Path) -> None:
    dashboard_src, messages_dir, policy, glossary = _fixture(tmp_path)
    _write(
        dashboard_src / "components" / "Bad.tsx",
        'export function Bad(){return <div>Health & Incidents</div>}\n',
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--strict",
            "--dashboard-src",
            str(dashboard_src),
            "--messages-dir",
            str(messages_dir),
            "--policy-doc",
            str(policy),
            "--glossary-doc",
            str(glossary),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "critical_english_visible_label" in completed.stdout


def test_glossary_requirement_is_checked(tmp_path: Path) -> None:
    dashboard_src = tmp_path / "apps" / "dashboard" / "src"
    messages_dir = dashboard_src / "messages"
    policy = tmp_path / "docs" / "production_10_10" / "german_only_ui_policy.md"
    glossary = tmp_path / "docs" / "production_10_10" / "german_ui_glossary.md"
    _write(policy, "# Policy ohne Glossar\n")
    _write(messages_dir / "de.json", "{}")
    _write(dashboard_src / "components" / "X.tsx", 'export function X(){return <div>Übersicht</div>}\n')

    summary = analyze_german_ui(
        dashboard_src=dashboard_src,
        messages_dir=messages_dir,
        policy_doc=policy,
        glossary_doc=glossary,
    )
    assert any(issue["code"] == "glossary_missing" for issue in summary["issues"])
