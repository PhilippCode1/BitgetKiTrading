#!/usr/bin/env python3
"""Validiert Bitget Key-Permission-Evidence (fail-closed, secret-redacted)."""

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

DEFAULT_TEMPLATE = ROOT / "docs" / "production_10_10" / "bitget_key_permission_evidence.template.json"
DEFAULT_OUTPUT_MD = ROOT / "reports" / "bitget_key_permission_evidence.md"
DEFAULT_OUTPUT_JSON = ROOT / "reports" / "bitget_key_permission_evidence.json"

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
        "schema_version": "bitget-key-permission-evidence-v2",
        "environment": "production",
        "mode": "live-readonly",
        "account_alias_redacted": "acct-***",
        "key_id_redacted": "key-***",
        "permissions_observed": ["read"],
        "read_permission": True,
        "trade_permission": False,
        "withdrawal_permission": False,
        "ip_allowlist_enabled": False,
        "account_protection_checked": False,
        "checked_at": "",
        "checked_by": "",
        "evidence_reference": "",
        "owner_review": {"signoff": False, "reviewer": "", "reviewed_at": ""},
        "status": "not_enough_evidence",
        "notes_de": "Template: echte Permission/IP-Allowlist/Account-Schutz-Evidence extern erheben; keine Secrets im Repo.",
    }


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = (
        "environment",
        "mode",
        "account_alias_redacted",
        "key_id_redacted",
        "permissions_observed",
        "read_permission",
        "trade_permission",
        "withdrawal_permission",
        "ip_allowlist_enabled",
        "account_protection_checked",
        "checked_at",
        "checked_by",
        "evidence_reference",
        "owner_review",
        "status",
    )
    blockers: list[str] = []
    warnings: list[str] = []
    for key in required:
        if key not in payload:
            blockers.append(f"missing_required_field:{key}")
    if payload.get("withdrawal_permission") is not False:
        blockers.append("p0_withdraw_permission_must_be_false")
    owner = payload.get("owner_review")
    owner_signoff = isinstance(owner, dict) and owner.get("signoff") is True
    if payload.get("trade_permission") is True and not owner_signoff:
        blockers.append("trade_permission_without_owner_signoff_not_verified")
    if payload.get("ip_allowlist_enabled") is not True:
        warnings.append("ip_allowlist_not_checked_not_enough_evidence")
    if payload.get("account_protection_checked") is not True:
        warnings.append("account_protection_not_checked_not_enough_evidence")
    is_template = any("CHANGE_ME" in str(v) for v in payload.values() if isinstance(v, str))
    if is_template or payload.get("status") in {"template", "not_enough_evidence"}:
        warnings.append("template_or_placeholder_evidence_not_enough_evidence")
    expected_redacted = ("account_alias_redacted", "key_id_redacted")
    for key in expected_redacted:
        val = str(payload.get(key, ""))
        if not val or ("*" not in val and "redacted" not in val.lower()):
            warnings.append(f"field_not_redacted_hint:{key}")
    final_status = "failed" if blockers else ("not_enough_evidence" if warnings else "verified")
    return {"status": final_status, "blockers": blockers, "warnings": warnings}


def render_markdown(payload: dict[str, Any], assessment: dict[str, Any], secret_issues: list[str]) -> str:
    lines = [
        "# Bitget Key Permission Evidence Check",
        "",
        "Status: prueft externe Permission-Evidence ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version', 'n/a')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Mode: `{payload.get('mode')}`",
        f"- Read Permission: `{payload.get('read_permission')}`",
        f"- Trade Permission: `{payload.get('trade_permission')}`",
        f"- Withdrawal Permission: `{payload.get('withdrawal_permission')}`",
        f"- IP-Allowlist: `{payload.get('ip_allowlist_enabled')}`",
        f"- Account-Schutz geprueft: `{payload.get('account_protection_checked')}`",
        f"- Ergebnis: `{assessment['status']}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in assessment["blockers"])
    if not assessment["blockers"]:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in assessment["warnings"])
    if not assessment["warnings"]:
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
            "- `verified` ersetzt keinen finalen Owner-Go/No-Go-Signoff.",
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
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(json.dumps(build_template(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote template: {args.write_template}")
        return 0

    payload = load_payload(args.evidence_json)
    assessment = _validate_payload(payload)
    secret_issues = secret_surface_issues(payload)
    result = {
        "ok": assessment["status"] == "verified" and not secret_issues,
        "status": assessment["status"],
        "blockers": list(assessment["blockers"]) + secret_issues,
        "warnings": list(assessment["warnings"]),
    }
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload, assessment, secret_issues), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "bitget_key_permission_evidence: "
            f"status={assessment['status']} blockers={len(result['blockers'])} warnings={len(result['warnings'])}"
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
