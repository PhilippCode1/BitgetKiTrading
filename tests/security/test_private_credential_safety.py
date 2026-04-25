from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from shared_py.private_credentials import (
    evaluate_private_credentials,
    is_placeholder_value,
    redact_sensitive_text,
    snapshot_to_payload,
)


def test_api_key_redacted() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="ABCD1234",
        bitget_api_secret="SECRET123456",
        bitget_api_passphrase="PASS1234",
        bitget_demo_enabled=False,
        execution_mode="paper",
        live_trade_enable=False,
        live_broker_enabled=False,
        read_only_checked=True,
        private_auth_ok=True,
        permission_trading=None,
        permission_withdrawal=None,
        revoked_or_expired=False,
        rotation_required=False,
        all_live_gates_ok=False,
    )
    assert snap.key_hint != "ABCD1234"


def test_api_secret_redacted() -> None:
    assert "SECRET123" not in redact_sensitive_text("api_secret=SECRET123")


def test_passphrase_redacted() -> None:
    assert "pass123" not in redact_sensitive_text("passphrase=pass123")


def test_authorization_header_redacted() -> None:
    out = redact_sensitive_text("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in out and "REDACTED" in out


def test_placeholder_not_valid() -> None:
    assert is_placeholder_value("CHANGE_ME_IN_SECRET_STORE") is True


def test_withdrawal_permission_blocks_live() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="AK12345678",
        bitget_api_secret="SS12345678",
        bitget_api_passphrase="PP12345678",
        bitget_demo_enabled=False,
        execution_mode="live",
        live_trade_enable=True,
        live_broker_enabled=True,
        read_only_checked=True,
        private_auth_ok=True,
        permission_trading=True,
        permission_withdrawal=True,
        revoked_or_expired=False,
        rotation_required=False,
        all_live_gates_ok=True,
    )
    assert snap.live_write_blocked is True
    assert snap.status == "withdrawal_permission_detected"


def test_trading_permission_alone_not_enough() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="AK12345678",
        bitget_api_secret="SS12345678",
        bitget_api_passphrase="PP12345678",
        bitget_demo_enabled=False,
        execution_mode="live",
        live_trade_enable=True,
        live_broker_enabled=True,
        read_only_checked=True,
        private_auth_ok=True,
        permission_trading=True,
        permission_withdrawal=False,
        revoked_or_expired=False,
        rotation_required=False,
        all_live_gates_ok=False,
    )
    assert snap.live_write_blocked is True


def test_demo_live_mix_blocks() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="AK12345678",
        bitget_api_secret="SS12345678",
        bitget_api_passphrase="PP12345678",
        bitget_demo_enabled=True,
        execution_mode="live",
        live_trade_enable=True,
        live_broker_enabled=True,
        read_only_checked=True,
        private_auth_ok=True,
        permission_trading=True,
        permission_withdrawal=False,
        revoked_or_expired=False,
        rotation_required=False,
        all_live_gates_ok=True,
    )
    assert snap.status in {"demo_only", "live_write_blocked"}
    assert snap.live_write_blocked is True


def test_revoked_expired_blocks() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="AK12345678",
        bitget_api_secret="SS12345678",
        bitget_api_passphrase="PP12345678",
        bitget_demo_enabled=False,
        execution_mode="live",
        live_trade_enable=True,
        live_broker_enabled=True,
        read_only_checked=True,
        private_auth_ok=False,
        permission_trading=False,
        permission_withdrawal=False,
        revoked_or_expired=True,
        rotation_required=False,
        all_live_gates_ok=True,
    )
    assert snap.live_write_blocked is True
    assert snap.status in {"expired_or_revoked", "invalid"}


def test_script_dry_run_no_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.runtime"
    env_file.write_text(
        "BITGET_API_KEY=AK_SECRET_VALUE\nBITGET_API_SECRET=REAL_SECRET\nBITGET_API_PASSPHRASE=REAL_PASS\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "private_bitget_credential_check.py"), "--dry-run", "--env-file", str(env_file)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REAL_SECRET" not in proc.stdout
    assert "REAL_PASS" not in proc.stdout


def test_main_console_payload_only_masked_hints() -> None:
    snap = evaluate_private_credentials(
        bitget_api_key="AK12345678",
        bitget_api_secret="SS12345678",
        bitget_api_passphrase="PP12345678",
        bitget_demo_enabled=False,
        execution_mode="paper",
        live_trade_enable=False,
        live_broker_enabled=False,
        read_only_checked=True,
        private_auth_ok=True,
        permission_trading=False,
        permission_withdrawal=False,
        revoked_or_expired=False,
        rotation_required=False,
        all_live_gates_ok=False,
    )
    payload = snapshot_to_payload(snap)
    hints = payload["credential_hints"]
    assert hints["api_secret"] != "SS12345678"
    assert "***" in hints["api_secret"]


def test_checker_detects_missing_doc_and_tests() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_private_credential_safety.py"), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    assert "issues" in payload
