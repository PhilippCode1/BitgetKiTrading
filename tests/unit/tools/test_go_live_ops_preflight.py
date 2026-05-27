"""Go-Live Ops-Preflight Tool."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "go_live_ops_preflight.py"


def _load_module():
    name = f"go_live_ops_preflight_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_production_template_passes_template_mode() -> None:
    mod = _load_module()
    env = mod.load_dotenv(REPO / ".env.production.example")
    issues = mod.evaluate_go_live_preflight(env, strict_runtime=False)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, [f"{e.code}: {e.message}" for e in errors]


def test_oidc_redirect_must_match_frontend() -> None:
    mod = _load_module()
    env = {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "PORTAL_AUTH_PROVIDER": "oidc",
        "OIDC_ISSUER": "https://auth.example.com",
        "OIDC_CLIENT_ID": "client",
        "OIDC_CLIENT_SECRET": "secret",
        "OIDC_REDIRECT_URI": "https://wrong.example.com/api/auth/callback",
        "OIDC_DEFAULT_TENANT_ID": "t-1",
        "FRONTEND_URL": "https://dashboard.example.com",
        "GO_LIVE_REQUIRE_STEP_UP": "true",
        "GO_LIVE_STEP_UP_TOTP_SECRET": "BASE32SECRET",
        "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT": "true",
        "VAULT_ADDR": "https://vault.example.com",
        "MODUL_MATE_GATE_TENANT_ID": "t-1",
        "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
        "GATEWAY_MANUAL_ACTION_REQUIRED": "true",
        "GATEWAY_MANUAL_ACTION_SECRET": "long-enough-secret-value",
        "GATEWAY_MOCK_BITGET_VERIFY": "false",
    }
    issues = mod.evaluate_go_live_preflight(env, strict_runtime=True)
    codes = {i.code for i in issues if i.severity == "error"}
    assert "oidc_redirect_frontend_mismatch" in codes


def test_vault_tenant_requires_modul_mate_tenant() -> None:
    mod = _load_module()
    env = {
        "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT": "true",
        "VAULT_ADDR": "https://vault.example.com",
    }
    issues = mod.evaluate_go_live_preflight(env, strict_runtime=False)
    codes = {i.code for i in issues if i.severity == "error"}
    assert "modul_mate_tenant_missing" in codes
