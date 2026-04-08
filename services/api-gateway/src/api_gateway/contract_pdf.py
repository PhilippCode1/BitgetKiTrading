"""PDF-Erzeugung fuer Kundenvertraege (fpdf2, Prompt 12)."""

from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from api_gateway.operator_health_pdf import (
    _ascii_fold,
    _register_report_fonts,
    _set_font,
)


def build_contract_pdf_bytes(
    *,
    title: str,
    body_text: str,
    tenant_id_masked: str,
    template_key: str,
    template_version: int,
    generated_at_iso: str,
    footer_extra: str | None = None,
) -> bytes:
    """
    Erzeugt ein einseitiges/mehrseitiges PDF aus Vorlagentext.

    footer_extra: z. B. Mock-E-Sign-Bestaetigung (wird sichtbar im Dokument).
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    family = _register_report_fonts(pdf)
    pdf.add_page()
    _set_font(pdf, family, "B", 13)
    t_title = _ascii_fold(title) if family == "Helvetica" else title
    pdf.multi_cell(0, 8, t_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _set_font(pdf, family, "", 8.5)
    meta = (
        f"Vorlage: {template_key} / v{template_version} | "
        f"Mandant (maskiert): {tenant_id_masked} | "
        f"Erzeugt (UTC): {generated_at_iso}"
    )
    m = _ascii_fold(meta) if family == "Helvetica" else meta
    pdf.multi_cell(0, 5, m, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    _set_font(pdf, family, "", 10)
    body = _ascii_fold(body_text) if family == "Helvetica" else body_text
    pdf.multi_cell(0, 5.5, body, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if footer_extra:
        pdf.ln(4)
        _set_font(pdf, family, "B", 9.5)
        fe = _ascii_fold(footer_extra) if family == "Helvetica" else footer_extra
        pdf.multi_cell(0, 5.5, fe, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
