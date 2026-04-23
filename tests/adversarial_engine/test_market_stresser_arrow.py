from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from adversarial_engine.arrow_ipc import decode_table_ipc_stream, encode_table_ipc_stream
from adversarial_engine.market_stresser import build_stress_tick_table, tensor_paths_to_numpy


def test_arrow_roundtrip_and_payload_shape() -> None:
    paths = torch.zeros(1, 64, 2)
    paths[0, :, 0] = torch.linspace(-0.02, 0.01, 64)
    paths[0, :, 1] = torch.linspace(0.5, -0.5, 64)
    r, d = tensor_paths_to_numpy(paths)
    tab = build_stress_tick_table(
        r,
        d,
        symbol="BTCUSDT",
        anchor_price=100_000.0,
        ts_start_ms=1_700_000_000_000,
        step_ms=200,
        toxicity=0.7,
    )
    raw = encode_table_ipc_stream(tab)
    assert len(raw) > 40
    back = decode_table_ipc_stream(raw)
    assert back.num_rows == tab.num_rows
    assert "last_pr" in back.column_names
