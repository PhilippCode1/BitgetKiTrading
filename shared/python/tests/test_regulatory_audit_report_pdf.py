from __future__ import annotations

from shared_py.regulatory_audit_report_pdf import (
    build_apex_regulatory_compliance_report_pdf_bytes,
    build_regulatory_audit_ledger_pdf_bytes,
    utc_now_iso,
)


def _sample_forensic_row() -> dict:
    return {
        "id": 1,
        "execution_id": "11111111-1111-1111-1111-111111111111",
        "signal_id": "22222222-2222-2222-2222-222222222222",
        "created_at": "2026-04-24T12:00:00+00:00",
        "golden_record": {
            "schema_version": "trade_lifecycle_golden_v1",
            "execution_id": "11111111-1111-1111-1111-111111111111",
            "signal_id": "22222222-2222-2222-2222-222222222222",
            "recorded_ts_ms": 1,
            "phases": {
                "signal": {
                    "core": {
                        "signal_id": "22222222-2222-2222-2222-222222222222",
                        "symbol": "BTCUSDT",
                    }
                },
                "ai_rationale": {
                    "explain_short": "Test short",
                    "confidence_0_1": 0.87,
                },
                "risk_signoff": {
                    "decision_reason": "limits_ok",
                    "trade_action": "open",
                    "metrics": {"limits_ok": True},
                },
                "exchange": {
                    "fills": [{"price": "95000.1", "size": "0.01", "side": "buy"}],
                },
            },
        },
        "verification": {
            "is_verified": True,
            "local_integrity_ok": True,
            "chain_link_ok": True,
        },
    }


def test_build_apex_regulatory_compliance_report_is_valid_pdf() -> None:
    tip = "a" * 64
    b = build_apex_regulatory_compliance_report_pdf_bytes(
        tenant_id="tenant-test",
        period_from_iso="2026-04-01T00:00:00Z",
        period_to_iso="2026-04-30T23:59:59Z",
        generated_at_iso=utc_now_iso(),
        forensics_rows=[_sample_forensic_row()],
        global_ledger_chain_tip_hash_hex=tip,
    )
    assert b[:4] == b"%PDF"
    assert b"%%EOF" in b
    # /Info Keywords: Klartext-Metadaten (Kettenspitze, Zeilenzahl)
    assert b"chain_tip_sha256_hex=" in b
    assert tip.encode("ascii") in b
    assert b"rows=1" in b


def test_build_regulatory_audit_ledger_pdf_bytes_still_works() -> None:
    b = build_regulatory_audit_ledger_pdf_bytes(
        title="Ledger",
        period_from_iso="a",
        period_to_iso="b",
        entries=[
            {
                "decision_id": "d1",
                "created_at": "t",
                "chain_hash_hex": "c1",
                "prev_chain_hash_hex": "p0",
                "signature_hex": "s" * 70,
                "consensus_status": "ok",
                "final_signal_action": "BUY",
            }
        ],
        generated_at_iso=utc_now_iso(),
    )
    assert b[:4] == b"%PDF"
