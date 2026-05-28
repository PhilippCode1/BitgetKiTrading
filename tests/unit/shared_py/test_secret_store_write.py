from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[3]
SHARED = REPO / "shared" / "python" / "src"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from shared_py.secret_store import VaultConfig, write_hashicorp_kv_v2  # noqa: E402


@patch("shared_py.secret_store.httpx.Client")
def test_write_hashicorp_kv_v2_success(mock_client_cls: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    cfg = VaultConfig(addr="http://127.0.0.1:8200", token="t", kv_mount="secret")
    ok = write_hashicorp_kv_v2(
        secret_path="bitget/t1/live",
        data={"api_key": "k"},
        cfg=cfg,
    )
    assert ok is True
    mock_client.post.assert_called_once()
