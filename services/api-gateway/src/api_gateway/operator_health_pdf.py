"""
Operator-Health-PDF: belegbare Evidenz fuer Mensch und KI
(Self-Healing / Follow-up-Coding).

Manifest, Evidence-Index, Remediation-Katalog, vollstaendige JSON-Corpora
(Health + Alerts + Outbox), chunkbar — reproduzierbar ohne Secrets.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Wird von Automation geparst — bei Format-Aenderung inkrementieren.
OPERATOR_PDF_EVIDENCE_SCHEMA = "operator-health-pdf-evidence-v2"

_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
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


def _text(pdf: FPDF, family: str, s: str) -> str:
    return _ascii_fold(s) if family == "Helvetica" else s


def _multi_cell_ln(pdf: FPDF, h: float, text: str) -> None:
    pdf.multi_cell(0, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _heading(pdf: FPDF, family: str, title: str, size: float = 12.0) -> None:
    _set_font(pdf, family, "B", size)
    _multi_cell_ln(pdf, size * 0.55, _text(pdf, family, title))
    _set_font(pdf, family, "", 9.5)


def _write_block(pdf: FPDF, family: str, text: str, size: float = 9.0) -> None:
    _set_font(pdf, family, "", size)
    t = _text(pdf, family, text)
    _multi_cell_ln(pdf, size * 0.45, t)


def _write_json_chunks(
    pdf: FPDF,
    family: str,
    obj: Any,
    *,
    chunk_chars: int = 42_000,
    font_size: float = 6.8,
    label: str = "JSON",
) -> None:
    """Grosses JSON seitenweise — vermeidet stilles Abschneiden."""
    try:
        raw = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    except TypeError:
        raw = json.dumps(str(obj), ensure_ascii=False)
    if not raw:
        _write_block(pdf, family, "(leer)", size=font_size)
        return
    n = max(1, (len(raw) + chunk_chars - 1) // chunk_chars)
    for i in range(n):
        if i > 0:
            pdf.add_page()
            _heading(pdf, family, f"{label} — Fortsetzung {i + 1}/{n}", size=10.0)
        chunk = raw[i * chunk_chars : (i + 1) * chunk_chars]
        _set_font(pdf, family, "", font_size)
        _multi_cell_ln(pdf, font_size * 0.42, _text(pdf, family, chunk))


def _iter_problem_integrations(matrix: dict[str, Any]) -> Iterable[dict[str, Any]]:
    rows = matrix.get("integrations")
    if not isinstance(rows, list):
        return
    bad = {"error", "misconfigured", "degraded", "not_configured"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        st = str(row.get("health_status") or "").strip().lower()
        if st in bad:
            yield row


def _report_fingerprint(
    health: dict[str, Any],
    open_alerts: Sequence[dict[str, Any]],
    outbox_rows: Sequence[dict[str, Any]],
    generated_at_iso: str,
) -> str:
    h = hashlib.sha256()
    h.update(generated_at_iso.encode())
    h.update(str(health.get("server_ts_ms")).encode())
    h.update(str(health.get("symbol") or "").encode())
    h.update(json.dumps(health.get("warnings") or [], sort_keys=True).encode())
    h.update(str(len(open_alerts)).encode())
    h.update(str(len(outbox_rows)).encode())
    return h.hexdigest()[:24]


def _build_manifest(
    *,
    report_id: str,
    fingerprint: str,
    generated_at_iso: str,
    health: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pdf_evidence_schema": OPERATOR_PDF_EVIDENCE_SCHEMA,
        "report_id": report_id,
        "content_fingerprint_sha256_24": fingerprint,
        "generated_at_utc": generated_at_iso,
        "primary_api": {
            "method": "GET",
            "path": "/v1/system/health",
            "auth": "Authorization: Bearer <operator_jwt> (wie Dashboard / Gateway)",
        },
        "secondary_api": [
            {"method": "GET", "path": "/v1/monitor/alerts/open"},
            {"method": "GET", "path": "/v1/alerts/outbox/recent"},
            {"method": "GET", "path": "/v1/system/health/operator-report.pdf"},
        ],
        "postgres_tables_cited": [
            "ops.alerts (state=open)",
            "alert.alert_outbox (recent)",
        ],
        "snapshot_fields": {
            "server_ts_ms": health.get("server_ts_ms"),
            "symbol": health.get("symbol"),
            "database": health.get("database"),
            "redis": health.get("redis"),
        },
        "reproduce_shell": [
            'curl -sS -H "Authorization: Bearer $TOKEN" '
            '"$API/v1/system/health" | jq .',
            'curl -sS -H "Authorization: Bearer $TOKEN" '
            '"$API/v1/monitor/alerts/open" | jq .',
            'curl -sS -H "Authorization: Bearer $TOKEN" '
            '"$API/v1/alerts/outbox/recent" | jq .',
        ],
    }


def _build_remediation_catalog(
    warnings_display: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in warnings_display:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "")
        machine = item.get("machine")
        if not isinstance(machine, dict):
            machine = {}
        entry: dict[str, Any] = {
            "evidence_ref": f"HEALTH-WARN-{code}",
            "warning_code": code,
            "problem_id": machine.get("problem_id"),
            "schema_version": machine.get("schema_version"),
            "severity": machine.get("severity"),
            "summary_en": machine.get("summary_en"),
            "facts": machine.get("facts"),
            "suggested_actions": machine.get("suggested_actions"),
            "verify_commands": machine.get("verify_commands"),
            "operator_title_de": item.get("title"),
            "operator_message_de": item.get("message"),
            "operator_next_step_de": item.get("next_step"),
            "related_services": item.get("related_services"),
        }
        out.append(entry)
    return out


def _build_evidence_index_lines(
    health: dict[str, Any],
    warnings_display: list[dict[str, Any]],
    open_alerts: Sequence[dict[str, Any]],
    outbox_rows: Sequence[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    warnings = health.get("warnings")
    if isinstance(warnings, list):
        for w in warnings:
            lines.append(f"[WARN-CODE] {w}")
    for item in warnings_display:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        m = item.get("machine") if isinstance(item.get("machine"), dict) else {}
        pid = m.get("problem_id", "?")
        sev = m.get("severity", "?")
        lines.append(f"[HEALTH-WARN-{code}] problem_id={pid} severity={sev}")
    services = health.get("services")
    if isinstance(services, list):
        for s in services:
            if not isinstance(s, dict):
                continue
            st = str(s.get("status") or "").lower()
            if st not in ("ok", "not_configured", ""):
                nm, lat = s.get("name"), s.get("latency_ms")
                lines.append(f"[SERVICE] {nm}: {st} latency_ms={lat}")
            elif st == "not_configured" and s.get("configured") is False:
                lines.append(f"[SERVICE] {s.get('name')}: not_configured")
    for a in open_alerts:
        if isinstance(a, dict):
            lines.append(
                f"[MONITOR-ALERT] key={a.get('alert_key')} sev={a.get('severity')} "
                f"title={a.get('title')}"
            )
    failed_out = [
        r
        for r in outbox_rows
        if isinstance(r, dict) and str(r.get("state")) == "failed"
    ]
    lines.append(f"[OUTBOX] rows_total={len(outbox_rows)} failed={len(failed_out)}")
    im = health.get("integrations_matrix")
    if isinstance(im, dict) and isinstance(im.get("integrations"), list):
        bad_n = sum(
            1
            for r in im["integrations"]
            if isinstance(r, dict)
            and str(r.get("health_status") or "").lower()
            in ("error", "misconfigured", "degraded", "not_configured")
        )
        lines.append(f"[INTEGRATIONS] rows={len(im['integrations'])} non_ok={bad_n}")
    else:
        lines.append("[INTEGRATIONS] matrix_missing_or_empty")
    return lines


def _build_complete_corpus(
    *,
    health: dict[str, Any],
    open_alerts: list[dict[str, Any]],
    outbox_rows: list[dict[str, Any]],
    generated_at_iso: str,
    report_id: str,
    fingerprint: str,
    remediation_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Ein einziges Objekt fuer LLM-Ingest: alles Belegbare in einem Baum."""
    return {
        "pdf_evidence_schema": OPERATOR_PDF_EVIDENCE_SCHEMA,
        "report_id": report_id,
        "content_fingerprint_sha256_24": fingerprint,
        "report_generated_at_utc": generated_at_iso,
        "instruction_for_automation_en": (
            "Use problem_id and verify_commands from remediation_catalog "
            "to validate fixes. Cross-check facts.warning_code with health.warnings. "
            "Service URLs: health.services[].url (no secrets). "
            "Monitor: ops.alerts; outbox: alert.alert_outbox."
        ),
        "health": health,
        "remediation_catalog": remediation_catalog,
        "open_alerts_ops_alerts": open_alerts,
        "alert_outbox_recent": outbox_rows,
    }


def build_operator_health_pdf(
    *,
    health: dict[str, Any],
    open_alerts: list[dict[str, Any]],
    outbox_rows: list[dict[str, Any]],
    generated_at_iso: str | None = None,
) -> bytes:
    ts = generated_at_iso or datetime.now(UTC).replace(microsecond=0).isoformat()
    report_id = str(uuid.uuid4())
    fingerprint = _report_fingerprint(health, open_alerts, outbox_rows, ts)
    manifest = _build_manifest(
        report_id=report_id, fingerprint=fingerprint, generated_at_iso=ts, health=health
    )
    wdisp: list[dict[str, Any]] = []
    raw_wd = health.get("warnings_display")
    if isinstance(raw_wd, list):
        wdisp = [x for x in raw_wd if isinstance(x, dict)]
    remediation_catalog = _build_remediation_catalog(wdisp)
    evidence_lines = _build_evidence_index_lines(
        health, wdisp, open_alerts, outbox_rows
    )
    complete_corpus = _build_complete_corpus(
        health=health,
        open_alerts=open_alerts,
        outbox_rows=outbox_rows,
        generated_at_iso=ts,
        report_id=report_id,
        fingerprint=fingerprint,
        remediation_catalog=remediation_catalog,
    )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(left=14, top=14, right=14)
    family = _register_report_fonts(pdf)
    pdf.add_page()

    _heading(
        pdf,
        family,
        "Operator Health — Evidenzbericht (KI / Automation)",
        size=14.0,
    )
    _write_block(
        pdf,
        family,
        "Zweck: vollstaendige, maschinell verwertbare Belege fuer Diagnose, Tickets "
        "und nachtraegliches Coding. Anhang Z enthaelt EIN JSON mit health + "
        "remediation_catalog + alerts + outbox (ohne Secrets).",
        size=9.0,
    )
    pdf.ln(2)
    _write_block(pdf, family, f"report_id: {report_id}")
    _write_block(pdf, family, f"fingerprint (sha256/24): {fingerprint}")
    _write_block(pdf, family, f"schema: {OPERATOR_PDF_EVIDENCE_SCHEMA}")
    _write_block(pdf, family, f"erstellt_utc: {ts}")

    pdf.ln(3)
    _heading(pdf, family, "A. Manifest (Maschinenlesbar)", size=11.5)
    _write_json_chunks(
        pdf,
        family,
        manifest,
        chunk_chars=38_000,
        font_size=7.0,
        label="Manifest JSON",
    )

    pdf.add_page()
    _heading(pdf, family, "B. Evidence-Index (flache Zeilen)", size=11.5)
    _write_block(
        pdf,
        family,
        "Jede Zeile ist ein Suchanker fuer Parser ([WARN-CODE], [SERVICE], ...).",
        size=8.5,
    )
    ev_text = "\n".join(evidence_lines) if evidence_lines else "(leer)"
    _write_block(pdf, family, ev_text, size=8.0)

    pdf.add_page()
    _heading(
        pdf,
        family,
        "C. Remediation-Katalog (machine-Bloecke zusammengefuehrt)",
        size=11.5,
    )
    _write_block(
        pdf,
        family,
        "Enthaelt problem_id, verify_commands, suggested_actions, facts — "
        "primaer fuer automatische Verifikation.",
        size=8.5,
    )
    _write_json_chunks(
        pdf,
        family,
        remediation_catalog,
        chunk_chars=40_000,
        font_size=6.8,
        label="Remediation-Katalog",
    )

    pdf.add_page()
    _heading(
        pdf,
        family,
        "D. Ausfuehrung und Freshness (execution, data_freshness)",
        size=11.5,
    )
    _write_json_chunks(
        pdf,
        family,
        {
            "execution": health.get("execution"),
            "data_freshness": health.get("data_freshness"),
            "market_universe": health.get("market_universe"),
        },
        chunk_chars=36_000,
        font_size=7.0,
        label="Execution/Freshness",
    )

    pdf.add_page()
    _heading(
        pdf,
        family,
        "E. Ops und Redis (ops, redis_streams_detail)",
        size=11.5,
    )
    _write_json_chunks(
        pdf,
        family,
        {
            "ops": health.get("ops"),
            "redis": health.get("redis"),
            "stream_lengths_top": health.get("stream_lengths_top"),
            "redis_streams_detail": health.get("redis_streams_detail"),
        },
        chunk_chars=40_000,
        font_size=6.8,
        label="Ops/Redis",
    )

    pdf.add_page()
    _heading(
        pdf,
        family,
        "F. Dienste (vollstaendige Probe-Objekte, inkl. url)",
        size=11.5,
    )
    services = health.get("services")
    _write_json_chunks(
        pdf,
        family,
        services if isinstance(services, list) else [],
        chunk_chars=40_000,
        font_size=6.5,
        label="services[]",
    )

    pdf.add_page()
    _heading(pdf, family, "G. Integrationsmatrix (komplett)", size=11.5)
    _write_json_chunks(
        pdf,
        family,
        health.get("integrations_matrix"),
        chunk_chars=45_000,
        font_size=6.5,
        label="integrations_matrix",
    )

    pdf.add_page()
    _heading(
        pdf,
        family,
        "H. warnings und warnings_display (vollstaendig)",
        size=11.5,
    )
    _write_json_chunks(
        pdf,
        family,
        {
            "warnings": health.get("warnings"),
            "warnings_display": health.get("warnings_display"),
        },
        chunk_chars=45_000,
        font_size=6.5,
        label="warnings",
    )

    pdf.add_page()
    _heading(pdf, family, "I. Offene Monitor-Alerts (Liste)", size=11.5)
    _write_json_chunks(
        pdf,
        family,
        open_alerts,
        chunk_chars=45_000,
        font_size=6.5,
        label="open_alerts",
    )

    pdf.add_page()
    _heading(pdf, family, "J. Alert-Outbox (juengste Zeilen)", size=11.5)
    _write_json_chunks(
        pdf,
        family,
        outbox_rows,
        chunk_chars=45_000,
        font_size=6.5,
        label="outbox",
    )

    pdf.add_page()
    _heading(
        pdf,
        family,
        "Z. ANHANG — Voll-Corpus (Single JSON fuer LLM / CI)",
        size=12.0,
    )
    _write_block(
        pdf,
        family,
        "Dieses Objekt bündelt health + remediation_catalog + alerts + outbox. "
        "Bei Tool-Extraktion bevorzugt diesen Block parsen.",
        size=8.5,
    )
    _write_json_chunks(
        pdf,
        family,
        complete_corpus,
        chunk_chars=38_000,
        font_size=6.2,
        label="COMPLETE_CORPUS_JSON",
    )

    return bytes(pdf.output())
