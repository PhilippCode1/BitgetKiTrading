from __future__ import annotations

from shared_py.observability.apex_trade_forensic_store import verify_row_integrity
from shared_py.observability.trade_lifecycle_audit import (
    TradeLifecycleAuditRecord,
    build_golden_record_from_timeline,
)
from shared_py.audit_ledger_chain import GENESIS_CHAIN_HASH, canonical_json_bytes, ledger_chain_digest


def test_build_golden_phases() -> None:
    t = {
        "execution_id": "00000000-0000-0000-0000-0000000000ab",
        "correlation": {"signal_id": "00000000-0000-0000-0000-0000000000cd"},
        "signal_context": {
            "signal_id": "00000000-0000-0000-0000-0000000000cd",
            "symbol": "BTCUSDT",
            "explain_short": "test",
        },
        "decision": {"leverage": 3, "approved_7x": True},
        "orders": [
            {
                "internal_order_id": "x",
                "exchange_order_id": "ex1",
                "status": "filled",
            }
        ],
        "fills": [{"price": "100", "size": "0.1", "exchange_trade_id": "t1"}],
    }
    g = build_golden_record_from_timeline(t)
    assert g["schema_version"] == "trade_lifecycle_golden_v1"
    assert "phases" in g
    assert g["phases"]["signal"]["core"]["symbol"] == "BTCUSDT"
    assert g["phases"]["exchange"]["orders"][0]["exchange_order_id"] == "ex1"
    r = TradeLifecycleAuditRecord.from_timeline(t)
    d = r.to_golden_dict()
    assert d["execution_id"] == g["execution_id"]


def test_verify_golden_row_local_integrity() -> None:
    golden = {
        "schema_version": "trade_lifecycle_golden_v1",
        "execution_id": "a",
        "a": 1,
    }
    prev = GENESIS_CHAIN_HASH
    ch = ledger_chain_digest(prev, canonical_json_bytes(golden))
    row = {
        "golden_record": golden,
        "prev_chain_checksum": prev,
        "chain_checksum": ch,
    }
    v = verify_row_integrity(row, expected_prev_link=prev)
    assert v["is_verified"] is True
    assert v["local_integrity_ok"] is True
    assert v["chain_link_ok"] is True
