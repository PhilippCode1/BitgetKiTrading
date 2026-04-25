from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from shared_py.single_admin_access import (
    SingleAdminContext,
    assert_single_admin_context,
    contains_forbidden_public_secret_env,
    is_server_only_secret_name,
    private_console_access_blocks_sensitive_action,
    redact_auth_error,
    requires_gateway_auth_message_de,
)


def _load_checker():
    root = Path(__file__).resolve().parents[2]
    checker_path = root / "tools" / "check_single_admin_access.py"
    spec = importlib.util.spec_from_file_location("check_single_admin_access", checker_path)
    if spec is None or spec.loader is None:
        raise AssertionError("checker import failed")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> Path:
    _write(tmp_path / "docs/production_10_10/single_admin_access_control.md", "Philipp Crljic")
    _write(tmp_path / "docs/api_gateway_security.md", "DASHBOARD_GATEWAY_AUTHORIZATION")
    _write(tmp_path / "tests/tools/test_check_single_admin_access.py", "x=1")
    _write(tmp_path / "tests/security/test_single_admin_access_contracts.py", "x=1")
    _write(tmp_path / "shared/python/src/shared_py/single_admin_access.py", "x=1")
    _write(
        tmp_path / "apps/dashboard/src/lib/gateway-bff.ts",
        'const msg = "DASHBOARD_GATEWAY_AUTHORIZATION fehlt";',
    )
    _write(tmp_path / "apps/dashboard/src/lib/server-env.ts", "gatewayAuthorizationHeader")
    _write(
        tmp_path / "config/gateway_settings.py",
        "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=False\ngateway_super_admin_subject='philipp'",
    )
    _write(
        tmp_path / "apps/dashboard/src/app/api/dashboard/admin/rules/route.ts",
        "import { requireOperatorGatewayAuth } from '@/lib/gateway-bff';\nrequireOperatorGatewayAuth();",
    )
    _write(tmp_path / ".env.production.example", "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=false\nDASHBOARD_GATEWAY_AUTHORIZATION=Bearer <gateway_jwt>\n")
    _write(tmp_path / ".env.local.example", "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=true\n")
    return tmp_path


def test_sensitive_route_without_auth_blocked() -> None:
    assert private_console_access_blocks_sensitive_action(has_auth=False, is_single_admin_ok=True) is True


def test_browser_env_with_secret_detected() -> None:
    assert contains_forbidden_public_secret_env("NEXT_PUBLIC_ADMIN_TOKEN=abc") is True


def test_legacy_admin_in_production_blocked() -> None:
    try:
        assert_single_admin_context(
            SingleAdminContext(
                admin_subject="philipp",
                caller_subject="philipp",
                production=True,
                legacy_admin_token_allowed=True,
            )
        )
    except PermissionError as exc:
        assert "legacy_admin" in str(exc)
    else:
        raise AssertionError("expected PermissionError")


def test_missing_dashboard_gateway_auth_has_german_error_marker() -> None:
    txt = Path("apps/dashboard/src/lib/gateway-bff.ts").read_text(encoding="utf-8")
    assert requires_gateway_auth_message_de(txt) is True


def test_internal_service_key_not_exposed_in_client_payload() -> None:
    assert is_server_only_secret_name("INTERNAL_API_KEY") is True
    assert is_server_only_secret_name("NEXT_PUBLIC_INTERNAL_API_KEY") is False


def test_local_dev_demo_allowed_but_production_not() -> None:
    assert private_console_access_blocks_sensitive_action(has_auth=True, is_single_admin_ok=True) is False
    assert private_console_access_blocks_sensitive_action(has_auth=True, is_single_admin_ok=False) is True


def test_auth_error_redacts_secrets() -> None:
    red = redact_auth_error("Authorization: Bearer abc123 TOKEN=foo")
    assert "abc123" not in red and "foo" not in red
    assert "REDACTED" in red


def test_single_admin_context_missing_blocks_sensitive_action() -> None:
    try:
        assert_single_admin_context(
            SingleAdminContext(
                admin_subject="philipp",
                caller_subject=None,
                production=False,
                legacy_admin_token_allowed=True,
            )
        )
    except ValueError as exc:
        assert "caller_subject_missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_no_customer_billing_roles_required_in_single_admin_helper() -> None:
    helper = Path("shared/python/src/shared_py/single_admin_access.py").read_text(encoding="utf-8").lower()
    assert "billing:admin" not in helper
    assert "customer_role_required" not in helper


def test_checker_detects_missing_doc_and_dangerous_env_names(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    (root / "docs/production_10_10/single_admin_access_control.md").unlink()
    _write(root / ".env.production.example", "NEXT_PUBLIC_AUTH_TOKEN=abc\nGATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=true\n")
    out = mod.analyze(root, strict=True)
    codes = {i["code"] for i in out["issues"]}
    assert "doc_missing" in codes
    assert "public_secret_env_name" in codes


def test_checker_json_parseable() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_single_admin_access.py"), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
