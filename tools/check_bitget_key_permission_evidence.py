#!/usr/bin/env python3
"""Validiert externe Bitget-Key-/Permission-Evidence ohne echte Secrets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.bitget.exchange_readiness import (  # noqa: E402
    READINESS_CONTRACT_VERSION,
    assess_external_key_evidence,
)

DEFAULT_TEMPLATE = ROOT / "docs" / "production_10_10" / "bitget_key_permission_evidence.template.json"

SECRET_LIKE_KEYS = ("api_key", "secret", "passphrase", "token", "password", "private_key")


def load_payload(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Evidence root muss ein JSON-Objekt sein.")
    return loaded


def secret_surface_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def build_template() -> dict[str, Any]:
    return {
        "schema_version": READINESS_CONTRACT_VERSION,
        "environment": "production",
        "account_mode": "live_candidate",
        "read_permission": True,
        "trade_permission": True,
        "withdrawal_permission": False,
        "ip_allowlist_enabled": False,
        "account_protection_enabled": False,
        "api_version": "v2",
        "instrument_scope": "",
        "reviewed_by": "",
        "reviewed_at": "",
        "evidence_reference": "",
        "owner_signoff": False,
        "api_key": "[REDACTED]",
        "api_secret": "[REDACTED]",
        "passphrase": "[REDACTED]",
        "notes_de": "Template: echte Werte extern pruefen; Secrets niemals im Repo speichern.",
    }


def render_markdown(payload: dict[str, Any], assessment: Any, secret_issues: list[str]) -> str:
    lines = [
        "# Bitget Key Permission Evidence Check",
        "",
        "Status: prueft externe Permission-Evidence ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Account Mode: `{payload.get('account_mode')}`",
        f"- Read Permission: `{payload.get('read_permission')}`",
        f"- Trade Permission: `{payload.get('trade_permission')}`",
        f"- Withdrawal Permission: `{payload.get('withdrawal_permission')}`",
        f"- IP-Allowlist: `{payload.get('ip_allowlist_enabled')}`",
        f"- Account-Schutz: `{payload.get('account_protection_enabled')}`",
        f"- Ergebnis: `{assessment.status}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in assessment.blockers)
    if not assessment.blockers:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in assessment.warnings)
    if not assessment.warnings:
        lines.append("- Keine Warnings.")
    lines.extend(["", "## Secret-Surface"])
    if secret_issues:
        lines.extend(f"- `{item}`" for item in secret_issues)
    else:
        lines.append("- Keine unredigierten Secret-Felder erkannt.")
    lines.extend(
        [
            "",
            "## Einordnung",
            "",
            "- `PASS_WITH_WARNINGS` oder `PASS` ersetzt keinen Owner-Go/No-Go-Signoff.",
            "- Withdrawal-Rechte sind immer P0-Blocker.",
            "- Echte API-Keys duerfen nicht in diesem JSON stehen.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-json", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(json.dumps(build_template(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote template: {args.write_template}")
        return 0

    payload = load_payload(args.evidence_json)
    assessment = assess_external_key_evidence(payload)
    secret_issues = secret_surface_issues(payload)
    result = {
        "ok": assessment.status == "PASS" and not secret_issues,
        "status": assessment.status,
        "blockers": list(assessment.blockers) + secret_issues,
        "warnings": list(assessment.warnings),
    }
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload, assessment, secret_issues), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "bitget_key_permission_evidence: "
            f"status={assessment.status} blockers={len(result['blockers'])} warnings={len(result['warnings'])}"
        )
        for blocker in result["blockers"]:
            print(f"BLOCKER {blocker}")
        for warning in result["warnings"]:
            print(f"WARNING {warning}")
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
