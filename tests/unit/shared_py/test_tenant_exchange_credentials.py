from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.tenant_exchange_credentials import (  # noqa: E402
    resolve_bitget_credentials_for_tenant,
    vault_secret_path_for_tenant,
)


def test_vault_path_convention() -> None:
    assert vault_secret_path_for_tenant("T-Tenant-1") == "bitget/t-tenant-1/live"


def test_resolve_from_global_env_single_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MODUL_MATE_GATE_TENANT_ID", "t-tenant-1")
    monkeypatch.setenv("BITGET_API_KEY", "k")
    monkeypatch.setenv("BITGET_API_SECRET", "s")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "p")
    bundle = resolve_bitget_credentials_for_tenant("t-tenant-1")
    assert bundle is not None
    assert bundle.source == "env_global"
    assert bundle.api_key == "k"


def test_resolve_fail_closed_for_foreign_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MODUL_MATE_GATE_TENANT_ID", "owner-tenant")
    monkeypatch.setenv("BITGET_API_KEY", "k")
    monkeypatch.setenv("BITGET_API_SECRET", "s")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "p")
    assert resolve_bitget_credentials_for_tenant("other-tenant") is None


def test_resolve_from_vault_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "true")
    monkeypatch.setenv("VAULT_MODE", "hashicorp")
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example")
    monkeypatch.setenv("VAULT_TOKEN", "tok")
    with patch(
        "shared_py.tenant_exchange_credentials.read_hashicorp_kv_v2",
        return_value={
            "api_key": "vk",
            "api_secret": "vs",
            "api_passphrase": "vp",
        },
    ):
        bundle = resolve_bitget_credentials_for_tenant("t-tenant-1")
    assert bundle is not None
    assert bundle.source == "vault_tenant"
    assert bundle.api_key == "vk"
