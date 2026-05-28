from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.verify_vault_tenant_credentials as mod


def test_verify_fails_on_placeholder_vault_token() -> None:
    env = {
        "VAULT_MODE": "hashicorp",
        "VAULT_ADDR": "https://vault.example.internal",
        "VAULT_TOKEN": "YOUR_API_KEY_HERE",
        "MODUL_MATE_GATE_TENANT_ID": "t-ops-1",
    }
    result = mod.verify_vault_tenant_credentials(tenant_id="t-ops-1", env=env)
    assert result["ok"] is False
    assert result["error"] == "vault_config_invalid"


@patch("tools.verify_vault_tenant_credentials.read_hashicorp_kv_v2")
def test_verify_passes_when_fields_present(mock_read) -> None:
    mock_read.return_value = {
        "api_key": "k",
        "api_secret": "s",
        "api_passphrase": "p",
    }
    env = {
        "VAULT_MODE": "hashicorp",
        "VAULT_ADDR": "https://vault.example.internal",
        "VAULT_TOKEN": "hvs.real-token-value",
        "MODUL_MATE_GATE_TENANT_ID": "t-ops-1",
    }
    result = mod.verify_vault_tenant_credentials(tenant_id="t-ops-1", env=env)
    assert result["ok"] is True
    assert result["vault_path"] == "bitget/t-ops-1/live"
