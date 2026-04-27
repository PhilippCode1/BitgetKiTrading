"""Smoke: Vertrags-PDF (Prompt 12) ist nicht leer und beginnt mit PDF-Header."""

from __future__ import annotations

from datetime import UTC, datetime

from api_gateway.contract_pdf import build_contract_pdf_bytes


def test_build_contract_pdf_bytes_non_empty_and_pdf_magic() -> None:
    iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    pdf = build_contract_pdf_bytes(
        title="Testtitel",
        body_text="Zeile1\nZeile2",
        tenant_id_masked="ab…cd",
        template_key="t",
        template_version=1,
        generated_at_iso=iso,
        footer_extra="Footer test",
    )
    assert len(pdf) > 200
    assert pdf[:4] == b"%PDF"
