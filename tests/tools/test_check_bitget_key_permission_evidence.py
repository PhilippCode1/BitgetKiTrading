from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_bitget_key_permission_evidence import build_template, secret_surface_issues


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_bitget_key_permission_evidence.py"
TEMPLATE = ROOT / "docs" / "production_10_10" / "bitget_key_permission_evidence.template.json"


def _valid_payload() -> dict[str, object]:
    payload = build_template()
    payload.update(
        {
            "ip_allowlist_enabled": True,
            "account_protection_checked": True,
            "checked_by": "external-security-review",
            "checked_at": "2026-04-26T00:00:00Z",
            "evidence_reference": "external-ticket-123",
            "owner_review": {"signoff": True, "reviewer": "Philipp", "reviewed_at": "2026-04-26T00:10:00Z"},
            "status": "verified",
            "account_alias_redacted": "acct-***",
            "key_id_redacted": "key-***",
        }
    )
    return payload


def test_template_is_valid_json_but_strict_blocks_external_gaps() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--evidence-json", str(TEMPLATE), "--strict", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert "ip_allowlist_not_checked_not_enough_evidence" in payload["warnings"]
    assert "account_protection_not_checked_not_enough_evidence" in payload["warnings"]


def test_strict_accepts_secret_free_external_evidence(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--evidence-json", str(path), "--strict", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["blockers"] == []


def test_unredacted_secret_like_fields_block() -> None:
    assert secret_surface_issues({"api_key": "real-looking-value"}) == ["secret_like_field_not_redacted:api_key"]
    assert secret_surface_issues({"api_key": "[REDACTED]", "api_secret": "not_stored_in_repo"}) == []
