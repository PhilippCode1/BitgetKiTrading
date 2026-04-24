"""
Regulatorischer PDF-Report: Forensik aus app.apex_trade_forensics
(Struktur TradeLifecycleAuditRecord) + Hash-Ketten-Status.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --- Branding (kann spaeter per Gateway-Config ueber Parameter ersetzt werden) ---
REPORT_COMPANY = "Apex Trade Intelligence"
REPORT_SUBTITLE = "Regulatory Audit & Forensic Attestation"
REPORT_FOOTER_LEGAL = (
    "Dieses Dokument fasst technische Ereignisse aus der Apex-Trade-Forensiktabelle "
    "und die kryptographische Kettendigest-Fingerprint zusammen. Keine Rechtsberatung."
)

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
    elif family == "Helvetica" and style == "I":
        pdf.set_font("Helvetica", "I", size)
    elif family == "Helvetica":
        pdf.set_font("Helvetica", "", size)
    elif family != "Helvetica" and style == "I":
        # TTF-Report: nur regulaer+Bold (kein add_font I -> FPDFException)
        pdf.set_font(family, "", size * 0.95)
    else:
        pdf.set_font(family, style, size)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _trunc(text: str, n: int) -> str:
    t = (text or "").replace("\n", " ").replace("\r", " ").strip()
    if len(t) <= n:
        return t or "—"
    return t[: n - 1] + "…"


def _m(o: Any) -> dict[str, Any]:
    return o if isinstance(o, dict) else {}


def _format_confidence(phase_ai: dict[str, Any]) -> str:
    c0 = phase_ai.get("confidence_0_1")
    if c0 is not None:
        try:
            return f"{float(c0):.4f}"
        except (TypeError, ValueError):
            return str(c0)[:20]
    return "—"


def _format_risk_rules(
    phase_risk: dict[str, Any],
    verification: dict[str, Any] | None,
) -> str:
    m = _m(phase_risk.get("metrics"))
    reason = str(phase_risk.get("decision_reason") or "").strip()
    bits: list[str] = []
    v = verification or {}
    if v.get("is_verified") is True:
        bits.append("Kette+Payload OK")
    elif v.get("is_verified") is False:
        bits.append("Integritaet: FEHLE")
    if m:
        for key in (
            "blocked",
            "reject_reason",
            "violations",
            "rule_hits",
            "limits_ok",
        ):
            if key in m and m[key] is not None:
                val = m[key]
                sval = (
                    str(val)[:120]
                    if not isinstance(val, dict | list)
                    else str(type(val).__name__)
                )
                bits.append(f"{key}={sval[:80]}")
    if not bits and reason:
        bits.append(reason)
    if not bits:
        dr = str(phase_risk.get("trade_action") or "").strip()
        return _trunc(dr, 200) if dr else "keine Detailmetrik"
    return _trunc(" | ".join(bits), 220)


def _final_fill_prices(phase_ex: dict[str, Any]) -> str:
    fills: Sequence[dict[str, Any]] = (
        phase_ex.get("fills")
        if isinstance(phase_ex.get("fills"), list)
        else ()
    )
    if not fills:
        return "—"
    last = _m(fills[-1] if isinstance(fills[-1], dict) else {})
    px = last.get("price")
    n = len(fills)
    return f"fills={n} last_px={px}" if px is not None else f"fills={n}"


def _format_pnl_column(phases: dict[str, Any], phase_ex: dict[str, Any]) -> str:
    pnl = phases.get("pnl_usd") or phases.get("attribution", {})
    if isinstance(pnl, dict) and pnl:
        s = pnl.get("net_usd") or pnl.get("pnl_net")
        if s is not None:
            return f"net={s}"
    raw = _m(phases).get("post_trade_review")
    if isinstance(raw, dict):
        s2 = raw.get("pnl_net_usd") or raw.get("label")
        if s2 is not None:
            return f"{s2}"[:32]
    return _final_fill_prices(phase_ex)


def _row_digest_for_table(row: dict[str, Any]) -> dict[str, str]:
    gr = _m(row.get("golden_record"))
    phases = _m(gr.get("phases")) if "phases" in gr else _m({})
    sig_core = _m(_m(phases.get("signal")).get("core"))
    sig = str(
        row.get("signal_id")
        or gr.get("signal_id")
        or sig_core.get("signal_id")
        or "—"
    )[:64]
    ts = str(row.get("created_at") or "—")[:32]
    ai = _m(
        phases.get("ai_rationale")
        if isinstance(phases.get("ai_rationale"), dict)
        else None
    )
    if not ai and phases:
        ai = _m(phases.get("ai", {}))
    conf = _format_confidence(ai)
    rsk = _m(phases.get("risk_signoff"))
    v = row.get("verification")
    vdict = v if isinstance(v, dict) else None
    risk_t = _format_risk_rules(rsk, vdict)
    pex = _m(phases.get("exchange"))
    pnl_col = _format_pnl_column(phases, pex)
    ex_short = _trunc(str(ai.get("explain_short") or "—"), 50)
    v_ok = (vdict or {}).get("is_verified")
    if v_ok is True:
        ver = "OK"
    elif v_ok is False:
        ver = "Fehler"
    else:
        ver = "—"
    return {
        "signal_id": _trunc(sig, 20),
        "ts": ts,
        "conf": conf,
        "ai": ex_short,
        "risk": risk_t,
        "fill_pnl": pnl_col,
        "verify": ver,
    }


def attach_verified_forensics(
    rows: list[dict[str, Any]],
    conn: Any,
) -> list[dict[str, Any]]:
    """
    Verknuepft jede Zeile mit ``verify_apex_row_with_ledger``
    (Ketten-Nachvollzug in id-Reihenfolge).
    """
    from shared_py.observability.apex_trade_forensic_store import (  # noqa: PLC0415
        verify_apex_row_with_ledger,
    )

    return [verify_apex_row_with_ledger(conn, row) for row in rows]


def build_apex_regulatory_compliance_report_pdf_bytes(
    *,
    tenant_id: str,
    period_from_iso: str,
    period_to_iso: str,
    generated_at_iso: str,
    forensics_rows: list[dict[str, Any]],
    global_ledger_chain_tip_hash_hex: str | None = None,
    company_title: str = REPORT_COMPANY,
    product_subtitle: str = REPORT_SUBTITLE,
) -> bytes:
    """
    Landscape-Report: Tabelle (Signale, KI, Risk, P&L/Fills, Verifikation) und
    Fingerprint (Spitze der globalen trade-forensic Hash-Kette) am Ende.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_compression(False)
    ktip = (global_ledger_chain_tip_hash_hex or "none").strip() or "none"
    # Klartext in /Info: revisionssichere Suche/Tests ohne Stream-Parsing
    meta_tid = _ascii_fold(_trunc(tenant_id, 64))
    pdf.set_title(
        f"apex-forensic-audit:tenant={meta_tid}:n={len(forensics_rows)}"
    )
    pdf.set_keywords(
        f"schema=apex-forensic-report-v1;rows={len(forensics_rows)};"
        f"chain_tip_sha256_hex={ktip}"
    )
    pdf.set_creator("shared_py.regulatory_audit_report_pdf")
    pdf.set_auto_page_break(auto=True, margin=16)
    family = _register_report_fonts(pdf)
    left = pdf.l_margin

    def _t(s: str) -> str:
        if family == "Helvetica":
            return _ascii_fold(s)
        return s

    def _h_line(text: str, *, size: float, bold: bool = False) -> None:
        st = "B" if bold else ""
        _set_font(pdf, family, st, size)
        pdf.multi_cell(0, 5.2, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.add_page()
    _h_line(company_title, size=16, bold=True)
    _h_line(product_subtitle, size=11, bold=True)
    _set_font(pdf, family, "", 9.4)
    tid_show = _trunc(tenant_id, 64)
    meta = (
        f"Mandant: {tid_show} | "
        f"Berichtszeitraum: {period_from_iso} – {period_to_iso} | "
        f"Erstellt (UTC): {generated_at_iso} | "
        f"Saetze: {len(forensics_rows)}"
    )
    pdf.multi_cell(0, 5, _t(meta), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    n_ok = sum(
        1
        for r in forensics_rows
        if _m(
            r.get("verification") if isinstance(r.get("verification"), dict) else {}
        ).get("is_verified")
        is True
    )
    summ = (
        f"Krypt. Verifikation: {n_ok} / {len(forensics_rows)} "
        f"Zeilen bestaetigt (Payload+Kettenlink)."
    )
    _set_font(pdf, family, "I", 8.5)
    pdf.multi_cell(0, 4, _t(summ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Tabelle: Breiten summieren = ca. 277mm bei L margin
    headers = [
        "Signal / Ref.",
        "Zeit (UTC)",
        "KI-Conf. 0-1",
        "KI (Kurz)",
        "Risk / Regeln + Sign-Off",
        "P&L / Fills",
        "Kette",
    ]
    w = (34, 34, 22, 50, 83, 34, 18)
    _set_font(pdf, family, "B", 7.0)
    pdf.set_x(left)
    for i, h in enumerate(headers):
        pdf.cell(w[i], 8, _t(h), border=1, align="C")
    pdf.ln(8)
    _set_font(pdf, family, "", 6.2)
    for r in forensics_rows:
        if pdf.get_y() > 185:
            pdf.add_page()
            _set_font(pdf, family, "B", 7.0)
            pdf.set_x(left)
            for i, h in enumerate(headers):
                pdf.cell(w[i], 8, _t(h), border=1, align="C")
            pdf.ln(8)
            _set_font(pdf, family, "", 6.2)
        d = _row_digest_for_table(r)
        cells = [
            _trunc(d["signal_id"], 20),
            _trunc(d["ts"], 30),
            d["conf"],
            _trunc(d["ai"], 44),
            _trunc(d["risk"], 100),
            _trunc(d["fill_pnl"], 32),
            d["verify"],
        ]
        pdf.set_x(left)
        for i, c in enumerate(cells):
            align = "C" if i in (2, 6) else "L"
            pdf.cell(w[i], 8, _t(str(c)), border=1, align=align)
        pdf.ln(8)

    pdf.ln(6)
    _set_font(pdf, family, "B", 11)
    fp_title = "Digitaler Fingerabdruck (gesamte Trade-Hash-Kette)"
    pdf.multi_cell(0, 5.5, _t(fp_title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _set_font(pdf, family, "", 8.5)
    na_tip = "n/a (Tabelle leer / keine Kettenspitze)"
    tip = (global_ledger_chain_tip_hash_hex or "").strip() or na_tip
    monosp = (
        f"letzter chain_checksum (Apex-Trade-Forensik, global, hex):  {tip}"
    )
    pdf.multi_cell(0, 4.2, _t(monosp), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _set_font(pdf, family, "I", 7.8)
    foot = _t(
        f"{REPORT_FOOTER_LEGAL}  "
        f"Document digest: SHA256-Kette laut app.apex_trade_forensics, "
        f"Spez. Migrations-626."
    )
    pdf.multi_cell(0, 3.6, foot, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


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
    Kompaktliste Apex-Audit-Entscheidungen inkl. Hash-Spalten (Operatorkontexte).

    ``entries``: je Zeile u. a. ``decision_id``, ``created_at``,
    ``chain_hash_hex``, ``prev_chain_hash_hex``, ``signature_hex``,
    ``consensus_status``, ``final_signal_action``.
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
