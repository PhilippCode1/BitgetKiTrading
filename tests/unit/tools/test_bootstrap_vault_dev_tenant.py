from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]


def test_bootstrap_requires_bitget_credentials(tmp_path: Path) -> None:
    tools = REPO / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import bootstrap_vault_dev_tenant as mod

    env_file = tmp_path / "vault.env"
    env_file.write_text(
        "\n".join(
            (
                "VAULT_MODE=hashicorp",
                "VAULT_ADDR=http://127.0.0.1:8200",
                "VAULT_TOKEN=dev-root-token",
                "MODUL_MATE_GATE_TENANT_ID=t-dev-1",
            )
        ),
        encoding="utf-8",
    )
    result = mod.bootstrap_vault_tenant(
        tenant_id="t-dev-1",
        env_files=[env_file],
        verify=False,
    )
    assert result["ok"] is False
    assert result["error"] == "bitget_credentials_missing"


@patch("bootstrap_vault_dev_tenant.write_hashicorp_kv_v2", return_value=True)
def test_bootstrap_writes_when_credentials_present(
    mock_write,
    tmp_path: Path,
) -> None:
    tools = REPO / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import bootstrap_vault_dev_tenant as mod

    env_file = tmp_path / "all.env"
    env_file.write_text(
        "\n".join(
            (
                "VAULT_MODE=hashicorp",
                "VAULT_ADDR=http://127.0.0.1:8200",
                "VAULT_TOKEN=dev-root-token",
                "MODUL_MATE_GATE_TENANT_ID=t-dev-1",
                "BITGET_API_KEY=k",
                "BITGET_API_SECRET=s",
                "BITGET_API_PASSPHRASE=p",
            )
        ),
        encoding="utf-8",
    )
    result = mod.bootstrap_vault_tenant(
        tenant_id="t-dev-1",
        env_files=[env_file],
        verify=False,
    )
    assert result["ok"] is True
    mock_write.assert_called_once()
