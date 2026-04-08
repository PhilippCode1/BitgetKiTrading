"""Tests fuer shared_py.commercial_data_model (Prompt 4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared_py.commercial_data_model import (
    COMMERCIAL_DATA_MODEL_VERSION,
    DE_VAT_RATE_STANDARD,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalType,
    DocumentMetadata,
    DocumentType,
    InvoiceLineRecord,
    InvoiceLineType,
    InvoiceRecord,
    InvoiceStatus,
    OrderRecord,
    OrderSource,
    OrderStatus,
    OrderWalletKind,
    commercial_data_model_descriptor,
    invoice_lines_net_vat_gross_totals,
    invoice_may_be_mutated,
    net_profit_after_fees_cents,
    profit_share_fee_cents,
    vat_amounts_from_net_cents,
)


def test_vat_19_percent_from_net() -> None:
    out = vat_amounts_from_net_cents(10_000, DE_VAT_RATE_STANDARD)
    assert out["net_cents"] == 10_000
    assert out["vat_cents"] == 1_900
    assert out["gross_cents"] == 11_900


def test_vat_rejects_negative_net() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        vat_amounts_from_net_cents(-1)


def test_net_profit_after_fees() -> None:
    assert net_profit_after_fees_cents(5000, 200) == 4800


def test_profit_share_20_percent() -> None:
    assert profit_share_fee_cents(100_000, 2000) == 20_000


def test_profit_share_rejects_negative() -> None:
    with pytest.raises(ValueError):
        profit_share_fee_cents(-1, 100)


def test_invoice_line_totals() -> None:
    lines = [
        {"net_cents": 1000, "vat_cents": 190, "gross_cents": 1190},
        {"net_cents": 2000, "vat_cents": 380, "gross_cents": 2380},
    ]
    t = invoice_lines_net_vat_gross_totals(lines)
    assert t["net_cents"] == 3000
    assert t["vat_cents"] == 570
    assert t["gross_cents"] == 3570


def test_invoice_mutable_only_draft() -> None:
    assert invoice_may_be_mutated(InvoiceStatus.DRAFT) is True
    assert invoice_may_be_mutated(InvoiceStatus.ISSUED) is False


def test_invoice_record_roundtrip() -> None:
    inv = InvoiceRecord(
        id="inv-1",
        organization_id="org-1",
        customer_account_id="cust-1",
        invoice_number="MM-2026-0001",
        status=InvoiceStatus.ISSUED,
        subtotal_net_cents=10000,
        vat_amount_cents=1900,
        total_gross_cents=11900,
    )
    assert inv.currency == "EUR"


def test_invoice_line_with_metadata() -> None:
    line = InvoiceLineRecord(
        id="l1",
        invoice_id="inv-1",
        line_type=InvoiceLineType.SUBSCRIPTION,
        description="Monatsabo",
        unit_net_cents=5000,
        net_cents=5000,
        vat_cents=950,
        gross_cents=5950,
    )
    assert line.line_type == InvoiceLineType.SUBSCRIPTION


def test_order_record_demo() -> None:
    o = OrderRecord(
        id="o1",
        customer_account_id="c1",
        wallet_kind=OrderWalletKind.DEMO,
        client_order_id="cl-1",
        symbol="BTCUSDT",
        side="buy",
        type="market",
        status=OrderStatus.SUBMITTED,
        source=OrderSource.KI_SUGGESTION,
    )
    assert o.wallet_kind == OrderWalletKind.DEMO


def test_approval_record_requires_note() -> None:
    a = ApprovalRecord(
        id="a1",
        customer_account_id="c1",
        approval_type=ApprovalType.LIVE_TRADING,
        decision=ApprovalDecision.GRANTED,
        decided_at=datetime.now(timezone.utc),
        decided_by_user_id="admin-philipp",
        note="Freigabe nach Pruefung",
    )
    assert a.decision == ApprovalDecision.GRANTED


def test_document_metadata_sha256_length() -> None:
    h = "a" * 64
    d = DocumentMetadata(
        id="d1",
        owner_type="customer",
        owner_id="c1",
        doc_type=DocumentType.INVOICE_PDF,
        storage_key="s3://bucket/key",
        sha256=h,
    )
    assert len(d.sha256) == 64


def test_descriptor() -> None:
    d = commercial_data_model_descriptor()
    assert d["commercial_data_model_version"] == COMMERCIAL_DATA_MODEL_VERSION
    assert "0.19" in d["de_vat_rate_standard"]
