"""
Regulatorischer PDF-Report: Hash-Nachweise der Apex-Audit-Ledger-Kette.

Stilistisch angelehnt an ``api_gateway.contract_pdf`` / Operator-Health-PDF (fpdf2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
)


def _pick_font_paths() -> tuple[Path, Path] | None:
    for regular, bold in _FONT_CANDIDATES:
        pr, pb = Path(regular), Path(bold)
        if pr.is_file():
            bb = pb if pb.is_file() else pr
            return pr, bb
    win = Path(r"C:\Windows\Fonts\arial.ttf")
    if win.is_file():
        return win, win
    return None


def _ascii_fold(text: str) -> str:
    return (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
        .replace("„", '"')
        .replace("“", '"')
        .replace("–", "-")
        .replace("—", "-")
    )


def _register_report_fonts(pdf: FPDF) -> str:
    picked = _pick_font_paths()
    if picked is not None:
        reg, bold = picked
        pdf.add_font("Report", "", str(reg))
        pdf.add_font("Report", "B", str(bold))
        return "Report"
    return "Helvetica"


def _set_font(pdf: FPDF, family: str, style: str, size: float) -> None:
    if family == "Helvetica" and style == "B":
        pdf.set_font("Helvetica", "B", size)
    elif family == "Helvetica":
        pdf.set_font("Helvetica", "", size)
    else:
        pdf.set_font(family, style, size)


def build_regulatory_audit_ledger_pdf_bytes(
    *,
    title: str,
    period_from_iso: str,
    period_to_iso: str,
    entries: list[dict[str, Any]],
    generated_at_iso: str,
    footer_note: str | None = None,
) -> bytes:
    """
    ``entries``: je Zeile u. a. ``decision_id``, ``created_at``, ``chain_hash_hex``,
    ``prev_chain_hash_hex``, ``signature_hex``, ``consensus_status``, ``final_signal_action``.
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
        f"Zeitraum (Filter): {period_from_iso} .. {period_to_iso} | "
        f"Erzeugt (UTC): {generated_at_iso} | Eintraege: {len(entries)}"
    )
    m = _ascii_fold(meta) if family == "Helvetica" else meta
    pdf.multi_cell(0, 5, m, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    _set_font(pdf, family, "", 8)
    for i, row in enumerate(entries):
        if pdf.get_y() > 270:
            pdf.add_page()
            _set_font(pdf, family, "", 8)
        did = str(row.get("decision_id") or "")
        ch = str(row.get("chain_hash_hex") or "")
        prev = str(row.get("prev_chain_hash_hex") or "")
        sig = str(row.get("signature_hex") or "")
        sig_short = f"{sig[:48]}...{sig[-16:]}" if len(sig) > 64 else sig
        st = str(row.get("consensus_status") or "")
        act = str(row.get("final_signal_action") or "")
        ts = str(row.get("created_at") or "")
        block = (
            f"[{i + 1}] {ts}\n"
            f"  decision_id: {did}\n"
            f"  consensus: {st}  action: {act}\n"
            f"  prev_chain_hash: {prev}\n"
            f"  chain_hash: {ch}\n"
            f"  signature (ed25519): {sig_short}\n"
        )
        b = _ascii_fold(block) if family == "Helvetica" else block
        pdf.multi_cell(0, 4.2, b, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
    if footer_note:
        pdf.ln(3)
        _set_font(pdf, family, "I", 8)
        fn = _ascii_fold(footer_note) if family == "Helvetica" else footer_note
        pdf.multi_cell(0, 4, fn, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
