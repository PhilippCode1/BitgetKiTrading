from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.secret_store import (  # noqa: E402
    VaultConfig,
    hydrate_env_keys_from_vault,
    read_hashicorp_kv_v2,
    vault_config_from_env,
)


def test_vault_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_MODE", "hashicorp")
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example")
    monkeypatch.setenv("VAULT_TOKEN", "tok")
    cfg = vault_config_from_env()
    assert cfg is not None
    assert cfg.addr == "https://vault.example"
    assert cfg.kv_mount == "secret"


def test_read_hashicorp_kv_v2_parses_data() -> None:
    cfg = VaultConfig(addr="https://vault.example", token="tok", kv_mount="secret")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {"data": {"BITGET_API_KEY": "k", "BITGET_API_SECRET": "s"}}
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_resp
    with patch("shared_py.secret_store.httpx.Client", return_value=mock_client):
        data = read_hashicorp_kv_v2(secret_path="bitget/t1/live", cfg=cfg)
    assert data == {"BITGET_API_KEY": "k", "BITGET_API_SECRET": "s"}


def test_hydrate_env_keys_from_vault_sets_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BITGET_API_KEY", raising=False)
    cfg = VaultConfig(addr="https://vault.example", token="tok", kv_mount="secret")
    with patch(
        "shared_py.secret_store.read_hashicorp_kv_v2",
        return_value={"BITGET_API_KEY": "from-vault"},
    ):
        n = hydrate_env_keys_from_vault(("BITGET_API_KEY",), vault_path="global/bitget", cfg=cfg)
    assert n == 1
    assert os.environ.get("BITGET_API_KEY") == "from-vault"
