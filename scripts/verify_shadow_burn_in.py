#!/usr/bin/env python3
# ruff: noqa: E501
"""
Shadow-Burn-in-Verifier: Postgres, Markdown, optionales JSON; siehe `main`.

Eintrag: `python scripts/verify_shadow_burn_in.py --help` (u.a. `--strict`, JSON-Ausgabe).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Optional: Proben aus JSONB nur redigieren, falls wir Details ausgeben
try:
    from shared_py.observability.execution_forensic import redact_nested_mapping
except ImportError:  # Aufruf ohne venv-Package

    def redact_nested_mapping(obj: Any, **_: Any) -> Any:  # type: ignore[misc]
        return obj


_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_READINESS = _REPO / "READINESS_EVIDENCE.md"
SHADOW_CERTIFICATE_SCHEMA_VERSION = "shadow-burn-in-certificate-v1"
DEFAULT_CERTIFICATE_TEMPLATE = (
    _REPO / "docs" / "production_10_10" / "shadow_burn_in_certificate.template.json"
)
SECRET_LIKE_KEYS = ("database_url", "dsn", "password", "secret", "token", "api_key", "private_key")


def build_shadow_certificate_template() -> dict[str, Any]:
    return {
        "schema_version": SHADOW_CERTIFICATE_SCHEMA_VERSION,
        "environment": "shadow",
        "execution_mode": "shadow",
        "started_at": "",
        "ended_at": "",
        "duration_hours": None,
        "consecutive_calendar_days": 0,
        "session_clusters_observed": [],
        "stress_or_event_day_documented": False,
        "report_verdict": "PENDING",
        "report_sha256": "",
        "git_sha": "",
        "runtime_env_snapshot_sha256": "",
        "live_trade_enable": False,
        "shadow_trade_enable": False,
        "live_broker_enabled": False,
        "require_shadow_match_before_live": False,
        "operator_release_required": False,
        "execution_binding_required": False,
        "max_leverage": None,
        "symbols_observed": [],
        "market_families_observed": [],
        "playbook_families_observed": [],
        "candidate_for_live_count": 0,
        "shadow_only_count": 0,
        "do_not_trade_count": 0,
        "p0_incidents": 0,
        "p1_incidents": 0,
        "reconcile_failures": 0,
        "shadow_live_mismatches": 0,
        "open_critical_alerts": 0,
        "data_quality_failures": 0,
        "liquidity_gate_failures": 0,
        "risk_gate_failures": 0,
        "audit_sample_reviewed": False,
        "forensics_sample_reference": "",
        "reviewed_by": "",
        "reviewed_at": "",
        "evidence_reference": "",
        "owner_signoff": False,
        "database_url": "[REDACTED]",
        "notes_de": "Template: echten Shadow-Burn-in extern auswerten; Secrets niemals im Repo speichern.",
    }


def _non_negative_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _non_negative_int(data: dict[str, Any], key: str) -> int | None:
    number = _non_negative_number(data, key)
    return None if number is None else int(number)


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def certificate_secret_surface_issues(data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in data.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def assess_shadow_certificate(data: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    if not data:
        return "FAIL", ["shadow_certificate_missing"], []
    blockers: list[str] = []
    warnings: list[str] = []
    if data.get("schema_version") != SHADOW_CERTIFICATE_SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if data.get("environment") not in {"shadow", "staging_shadow", "production_shadow"}:
        blockers.append("environment_invalid")
    if data.get("execution_mode") != "shadow":
        blockers.append("execution_mode_not_shadow")
    if not str(data.get("started_at") or "").strip():
        blockers.append("started_at_missing")
    if not str(data.get("ended_at") or "").strip():
        blockers.append("ended_at_missing")
    duration = _non_negative_number(data, "duration_hours")
    if duration is None:
        blockers.append("duration_hours_missing")
    elif duration < 336:
        blockers.append("duration_less_than_14_days")
    days = _non_negative_int(data, "consecutive_calendar_days")
    if days is None or days < 14:
        blockers.append("consecutive_calendar_days_less_than_14")
    if len(set(_string_list(data, "session_clusters_observed"))) < 3:
        blockers.append("session_clusters_less_than_3")
    if data.get("stress_or_event_day_documented") is not True:
        blockers.append("stress_or_event_day_not_documented")
    if data.get("report_verdict") != "PASS":
        blockers.append("report_verdict_not_pass")
    if not str(data.get("report_sha256") or "").strip():
        blockers.append("report_sha256_missing")
    if not str(data.get("git_sha") or "").strip():
        blockers.append("git_sha_missing")
    if not str(data.get("runtime_env_snapshot_sha256") or "").strip():
        blockers.append("runtime_env_snapshot_sha256_missing")
    required_flags = (
        ("live_trade_enable", False, "live_trade_enable_not_false"),
        ("shadow_trade_enable", True, "shadow_trade_enable_not_true"),
        ("live_broker_enabled", True, "live_broker_enabled_not_true"),
        ("require_shadow_match_before_live", True, "require_shadow_match_before_live_not_true"),
        ("operator_release_required", True, "operator_release_required_not_true"),
        ("execution_binding_required", True, "execution_binding_required_not_true"),
    )
    for key, expected, code in required_flags:
        if data.get(key) is not expected:
            blockers.append(code)
    leverage = _non_negative_number(data, "max_leverage")
    if leverage is None:
        blockers.append("max_leverage_missing")
    elif leverage > 7:
        blockers.append("max_leverage_above_ramp_limit")
    for key, code in (
        ("symbols_observed", "symbols_observed_missing"),
        ("market_families_observed", "market_families_observed_missing"),
        ("playbook_families_observed", "playbook_families_observed_missing"),
    ):
        if not _string_list(data, key):
            blockers.append(code)
    for key, code in (
        ("candidate_for_live_count", "candidate_for_live_missing"),
        ("shadow_only_count", "shadow_only_missing"),
        ("do_not_trade_count", "do_not_trade_missing"),
    ):
        value = _non_negative_int(data, key)
        if value is None or value < 1:
            blockers.append(code)
    zero_required = (
        ("p0_incidents", "p0_incidents_present"),
        ("p1_incidents", "p1_incidents_present"),
        ("reconcile_failures", "reconcile_failures_present"),
        ("shadow_live_mismatches", "shadow_live_mismatches_present"),
        ("open_critical_alerts", "open_critical_alerts_present"),
        ("data_quality_failures", "data_quality_failures_present"),
        ("liquidity_gate_failures", "liquidity_gate_failures_present"),
        ("risk_gate_failures", "risk_gate_failures_present"),
    )
    for key, code in zero_required:
        value = _non_negative_int(data, key)
        if value is None or value > 0:
            blockers.append(code)
    if data.get("audit_sample_reviewed") is not True:
        blockers.append("audit_sample_not_reviewed")
    if not str(data.get("forensics_sample_reference") or "").strip():
        blockers.append("forensics_sample_reference_missing")
    if not str(data.get("reviewed_by") or "").strip():
        blockers.append("reviewer_missing")
    if not str(data.get("reviewed_at") or "").strip():
        blockers.append("reviewed_at_missing")
    if not str(data.get("evidence_reference") or "").strip():
        blockers.append("evidence_reference_missing")
    if data.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return status, blockers, warnings


def _certificate_markdown(data: dict[str, Any], status: str, blockers: list[str], warnings: list[str], secret_issues: list[str]) -> str:
    lines = [
        "# Shadow Burn-in Certificate Check",
        "",
        "Status: prueft externen Shadow-Burn-in-Nachweis ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{data.get('schema_version')}`",
        f"- Environment: `{data.get('environment')}`",
        f"- Execution Mode: `{data.get('execution_mode')}`",
        f"- Dauer Stunden: `{data.get('duration_hours')}`",
        f"- Kalendertage: `{data.get('consecutive_calendar_days')}`",
        f"- Session-Cluster: `{', '.join(_string_list(data, 'session_clusters_observed')) or 'missing'}`",
        f"- Report Verdict: `{data.get('report_verdict')}`",
        f"- Report SHA256: `{data.get('report_sha256') or 'missing'}`",
        f"- Ergebnis: `{status}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in blockers)
    if not blockers:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in warnings)
    if not warnings:
        lines.append("- Keine Warnings.")
    lines.extend(["", "## Secret-Surface"])
    lines.extend(f"- `{item}`" for item in secret_issues)
    if not secret_issues:
        lines.append("- Keine unredigierten Secret-Felder erkannt.")
    lines.extend(
        [
            "",
            "## Einordnung",
            "",
            "- Fixture- oder Dry-run-PASS reicht nicht fuer private Live-Freigabe.",
            "- Live bleibt `NO_GO`, bis ein echter Shadow-Burn-in mit 14 Tagen, Sessions, Report-SHA, Review und Owner-Signoff vorliegt.",
            "",
        ]
    )
    return "\n".join(lines)


def _fixture_verdict(data: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    hours = float(data.get("hours_observed") or data.get("duration_hours") or 0)
    if hours < 72:
        blockers.append("burn_in_less_than_72h")
    if int(data.get("p0_incidents", 0) or 0) > 0:
        blockers.append("p0_incident_present")
    if int(data.get("reconcile_failures", 0) or 0) > 0:
        blockers.append("reconcile_failures_present")
    if int(data.get("multi_asset_data_quality_failures", 0) or 0) > 0:
        blockers.append("multi_asset_data_quality_failures_present")
    if int(data.get("unexplained_no_trade_reasons", 0) or 0) > 0:
        warnings.append("unexplained_no_trade_reasons_present")
    if blockers:
        return "FAIL", blockers, warnings
    if warnings:
        return "PASS_WITH_WARNINGS", blockers, warnings
    return "PASS", blockers, warnings


def _fixture_markdown(
    data: dict[str, Any],
    *,
    verdict: str,
    blockers: list[str],
    warnings: list[str],
    git_sha: str,
) -> str:
    return "\n".join(
        [
            "# Shadow Burn-in Evidence",
            "",
            f"- Git SHA: `{git_sha}`",
            f"- Ergebnis: `{verdict}`",
            f"- Beobachtete Stunden: `{data.get('hours_observed') or data.get('duration_hours') or 0}`",
            f"- Multi-Asset-Datenqualitaet: `{data.get('multi_asset_data_quality_status', 'unknown')}`",
            f"- Reconcile Failures: `{data.get('reconcile_failures', 0)}`",
            f"- P0 Incidents: `{data.get('p0_incidents', 0)}`",
            f"- No-Trade-Gruende: `{data.get('no_trade_reason_count', 0)}`",
            "",
            "## Blocker",
            *(f"- `{item}`" for item in blockers),
            "",
            "## Warnings",
            *(f"- `{item}`" for item in warnings),
            "",
            "Live-Freigabe bleibt blockiert, solange kein echter PASS-Report fuer Philipp archiviert ist.",
            "",
        ]
    )


def _run_fixture_or_dry_run(
    *,
    input_json: Path | None,
    output_md: Path | None,
    dry_run: bool,
) -> int:
    data: dict[str, Any]
    if input_json is not None:
        data = json.loads(input_json.read_text(encoding="utf-8"))
    else:
        data = {
            "hours_observed": 0 if dry_run else 72,
            "multi_asset_data_quality_status": "not_checked",
            "multi_asset_data_quality_failures": 0,
            "reconcile_failures": 0,
            "p0_incidents": 0,
            "no_trade_reason_count": 0,
        }
    verdict, blockers, warnings = _fixture_verdict(data)
    if dry_run and input_json is None:
        verdict = "PASS_WITH_WARNINGS"
        blockers = []
        warnings.append("dry_run_no_runtime_evidence")
    body = _fixture_markdown(
        data,
        verdict=verdict,
        blockers=blockers,
        warnings=warnings,
        git_sha=_git_sha(),
    )
    print(body, end="")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(body, encoding="utf-8")
    return 0 if verdict in {"PASS", "PASS_WITH_WARNINGS"} else 1


def _read_env_dsn(p: Path, key: str = "DATABASE_URL") -> str | None:
    t = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(rf"^{re.escape(key)}=(.*)$", t, re.M)
    if not m:
        return None
    s = m.group(1).strip()
    if s.startswith(('"', "'")):
        s = s[1:-1] if len(s) >= 2 and s[0] == s[-1] else s
    s = s.split("#", 1)[0].strip()
    return s or None


def _git_sha() -> str:
    s = (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or "").strip()
    if len(s) >= 7:
        return s[:40]
    try:
        p = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO,
            timeout=8,
        )
        if p.returncode == 0 and p.stdout:
            return p.stdout.strip()[:40]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unbekannt"


@contextmanager
def _connect(
    dsn: str,
):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        raise SystemExit(
            "psycopg fehlt — pip install psycopg[binary] bzw. requirements"
        ) from e
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=20) as conn:
        yield conn


def _safe_table(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        """
        SELECT EXISTS(
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    ).fetchone()
    return bool(r) and (list(r.values())[0] is True)


_FAT_TOKENS = re.compile(
    r"fat|finger|typo|fingerprint|oops|abgelehnt|reject.*size|notional.*(limit|exceed)|"
    r"size.*(invalid|exceed)|precision|step.*size|min.*notional",
    re.IGNORECASE,
)


_OUTAGE_REASON_RE = re.compile(
    r"stale|timeout|unavailable|upstream|reconcile.*fail|health.*fail|"
    r"service.*down|data.*stale|stream.*lag",
    re.IGNORECASE,
)


def _check_suspicious_blocks(
    conn: Any, since: datetime, until: datetime, strict: bool
) -> tuple[bool, str, list[dict[str, Any]]]:
    """(ok, summary, beispielzeilen), ok False bei Verdacht Fat-Finger auf blocked paths."""
    if not _safe_table(conn, "live", "execution_decisions"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.execution_decisions` fehlt — Block/Reason-Audit unbekannt.",
                [],
            )
        return (
            True,
            "Tabelle `live.execution_decisions` fehlt — Prüfung übersprungen",
            [],
        )
    rows = conn.execute(
        """
        SELECT execution_id, decision_action, decision_reason, symbol, created_ts, payload_json
        FROM live.execution_decisions
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND decision_action = 'blocked'
        ORDER BY created_ts DESC
        LIMIT 200
        """,
        (since, until),
    ).fetchall()
    hits: list[dict[str, Any]] = []
    for row in rows:
        reason = str(row.get("decision_reason") or "")
        pjson = row.get("payload_json")
        if _FAT_TOKENS.search(reason) or _FAT_TOKENS.search(str(pjson or "")):
            hits.append(
                {
                    "execution_id": str(row.get("execution_id")),
                    "decision_reason": reason[:500],
                    "symbol": row.get("symbol"),
                    "created_ts": row.get("created_ts"),
                }
            )
    if hits:
        return (
            False,
            f"{len(hits)} blockierte Pfade **mit Verdacht** auf Eingabe-/Betrags-Problem (Stichprobe unten).",
            hits[:12],
        )
    n = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM live.execution_decisions
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND decision_action = 'blocked'
        """,
        (since, until),
    ).fetchone()
    c = int((n or {}).get("c", 0))
    return (
        True,
        f"Keine blockierten Entscheidungen mit Fat-Finger-/Betragsmustern. "
        f"Ordinary risk `blocked` (n={c}) in Ordnung für manuelle Sichtprüfung.",
        [],
    )


def _check_paper_auto_blocked(
    conn: Any, since: datetime, until: datetime, strict: bool
) -> tuple[bool, str, int]:
    if not _safe_table(conn, "paper", "strategy_events"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `paper.strategy_events` fehlt (AUTO_BLOCKED nicht belegbar).",
                0,
            )
        return (
            True,
            "paper.strategy_events fehlt — Prüfung übersprungen",
            0,
        )
    to_ms = int(until.timestamp() * 1000)
    from_ms = int(since.timestamp() * 1000)
    n = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM paper.strategy_events
        WHERE ts_ms >= %s
          AND ts_ms <= %s
          AND type = 'AUTO_BLOCKED'
        """,
        (from_ms, to_ms),
    ).fetchone()
    c = int((n or {}).get("c", 0))
    ok = True
    msg = f"AUTO_BLOCKED-Paper-Events: {c} (erwartet bei Gates; kein autonomer Fail ohne muster). "
    return (ok, msg, c)


def _check_alerts(
    conn: Any, since: datetime, now: datetime, strict: bool
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "ops", "alerts"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `ops.alerts` fehlt — Alert-Pfad für Burn-in nicht sichtbar.",
                [],
            )
        return (True, "ops.alerts fehlt — Prüfung übersprungen", [])
    rows = conn.execute(
        """
        SELECT alert_key, severity, title, message, state, created_ts, updated_ts
        FROM ops.alerts
        WHERE state = 'open'
          AND severity IN ('warn', 'critical')
          AND created_ts >= %s
          AND created_ts <= %s
        ORDER BY
          CASE severity WHEN 'critical' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END,
          created_ts DESC
        """,
        (since, now),
    ).fetchall()
    if not rows:
        return (
            True,
            "Keine offenen P0/P1-äquivalenten Alerts (warn/critical) im Fenster.",
            [],
        )
    out = []
    for r in rows:
        p0 = "P0" if r.get("severity") == "critical" else "P1"
        out.append(
            {
                "kategorie": p0,
                "alert_key": r.get("alert_key"),
                "title": (r.get("title") or "")[:300],
                "message": (r.get("message") or "")[:400],
                "created_ts": r.get("created_ts"),
            }
        )
    return (False, f"{len(out)} offene warn/critical-Alert(s) im Fenster", out)


def _check_stream_and_service_lag(
    conn: Any,
    since: datetime,
    now: datetime,
    max_lag_ms: int,
    strict: bool,
) -> tuple[bool, str, list[dict[str, Any]]]:
    from psycopg import errors as pg_errors

    if not _safe_table(conn, "ops", "stream_checks") and not _safe_table(
        conn, "ops", "service_checks"
    ):
        if strict:
            return (
                False,
                "NO_EVIDENCE: weder `ops.stream_checks` noch `ops.service_checks` — Pipeline-Lag unbekannt.",
                [],
            )
    bad: list[dict[str, Any]] = []
    if _safe_table(conn, "ops", "stream_checks"):
        try:
            rows = conn.execute(
                """
            SELECT id, stream, group_name, lag, status, ts, details
            FROM ops.stream_checks
            WHERE ts >= %s AND ts <= %s
              AND (
                status = 'fail'
                OR (lag IS NOT NULL AND lag::bigint > %s)
              )
            ORDER BY ts DESC
            LIMIT 50
            """,
                (since, now, max_lag_ms),
            ).fetchall()
        except pg_errors.UndefinedTable:
            rows = []
        for r in rows:
            bad.append(
                {
                    "quelle": "ops.stream_checks",
                    "stream": r.get("stream"),
                    "lag": r.get("lag"),
                    "status": r.get("status"),
                    "ts": r.get("ts"),
                }
            )
    if _safe_table(conn, "ops", "service_checks"):
        try:
            rows2 = conn.execute(
                """
            SELECT service_name, check_type, status, latency_ms, ts, details
            FROM ops.service_checks
            WHERE ts >= %s AND ts <= %s
              AND (
                status = 'fail'
                OR (latency_ms IS NOT NULL AND latency_ms > %s)
              )
            ORDER BY ts DESC
            LIMIT 50
            """,
                (since, now, max_lag_ms),
            ).fetchall()
        except pg_errors.UndefinedTable:
            rows2 = []
        for r in rows2:
            bad.append(
                {
                    "quelle": "ops.service_checks",
                    "service": r.get("service_name"),
                    "latency_ms": r.get("latency_ms"),
                    "status": r.get("status"),
                    "ts": r.get("ts"),
                }
            )
    if not bad:
        return (
            True,
            f"Keine Stream-/Service-Pfade mit lag/latency_ms > {max_lag_ms} oder status=fail.",
            [],
        )
    return (
        False,
        f"Pipeline/Health: {len(bad)} Ereignis(se) mit Überschreitung oder fail.",
        bad,
    )


def _check_heartbeat_gaps(
    conn: Any,
    since: datetime,
    now: datetime,
    max_gap_sec: int,
    strict: bool,  # noqa: ARG001 — reserved for stricter Lücken-Regeln
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "ops", "service_checks"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: Tabelle `ops.service_checks` fehlt (Heartbeat/Health nicht belegbar).",
                [],
            )
        return (True, "ops.service_checks fehlt — Heartbeat-Prüfung übersprungen", [])
    rows = conn.execute(
        """
        SELECT service_name,
               COALESCE(MAX(gap_s), 0)::bigint AS max_gap_s
        FROM (
            SELECT
              service_name,
              EXTRACT(
                EPOCH FROM (t.ts - t.prev)
              )::bigint AS gap_s
            FROM (
                SELECT
                  service_name,
                  ts,
                  LAG(ts) OVER (PARTITION BY service_name ORDER BY ts) AS prev
                FROM ops.service_checks
                WHERE ts >= %s
                  AND ts <= %s
                  AND check_type = 'health'
            ) t
            WHERE t.prev IS NOT NULL
        ) g
        GROUP BY service_name
        """,
        (since, now),
    ).fetchall()
    if not rows:
        return (
            False,
            "Keine `ops.service_checks` health-Zeilen im Fenster — Heartbeat nicht belegt.",
            [],
        )
    problems = []
    for r in rows:
        g = int(r.get("max_gap_s") or 0)
        if g > max_gap_sec:
            problems.append(
                {
                    "service_name": r.get("service_name"),
                    "max_gap_s": g,
                }
            )
    if not problems:
        return (
            True,
            f"Health-Check-Luecken <= {max_gap_sec}s je Service (Partition health).",
            rows,
        )
    return (False, f"Heartbeat: max_gap > {max_gap_sec}s bei Dienst(en)", problems)


def _check_paper_slippage_bps(
    conn: Any,
    from_ms: int,
    to_ms: int,
    max_p95_bps: float,
    max_abs_bps: float,
    strict: bool,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Fills vs. zuletzt bekannten Ticker (Mark/Last) vor fill.ts_ms. Ohne Ticker-Referenz
    zählt die Zeile nicht für Slippage-Statistik.
    """
    if not all(
        _safe_table(conn, s, t)
        for s, t in (("paper", "fills"), ("paper", "positions"), ("tsdb", "ticker"))
    ):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `paper.fills`/`paper.positions`/`tsdb.ticker` unvollständig — "
                "Slippage-KPI nicht herleitbar.",
                {},
            )
        return (
            True,
            "paper.fills/positions oder tsdb.ticker fehlt — Slippage-Pruefung uebersprungen",
            {},
        )
    from psycopg import errors as pg_errors

    try:
        rows = conn.execute(
            """
            WITH base AS (
              SELECT
                f.fill_id,
                f.ts_ms,
                f.price::float8 AS fill_px,
                p.symbol,
                t.last_pr::float8,
                t.mark_price::float8,
                t.ts_ms AS ref_ts_ms
              FROM paper.fills f
              JOIN paper.positions p ON p.position_id = f.position_id
              LEFT JOIN LATERAL (
                SELECT last_pr, mark_price, ts_ms
                FROM tsdb.ticker
                WHERE symbol = p.symbol
                  AND ts_ms <= f.ts_ms
                ORDER BY ts_ms DESC
                LIMIT 1
              ) t ON true
              WHERE f.ts_ms >= %s
                AND f.ts_ms <= %s
            ),
            s AS (
              SELECT
                *,
                COALESCE(
                  mark_price, last_pr, NULL
                ) AS ref_px
              FROM base
            )
            SELECT fill_id, ts_ms, fill_px, symbol, ref_px, ref_ts_ms, last_pr, mark_price
            FROM s
            """,
            (from_ms, to_ms),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return (True, "Slippage: benoetigte Tabelle fehlt — uebersprungen", {})

    bps_list: list[float] = []
    for r in rows or ():
        ref = r.get("ref_px")
        fp = r.get("fill_px")
        if ref is None or fp is None or float(ref) <= 0:
            continue
        bps = abs((float(fp) - float(ref)) / float(ref)) * 10_000.0
        bps_list.append(bps)

    if not bps_list:
        n = len(rows or [])
        if n == 0:
            if strict:
                return (
                    False,
                    "NO_EVIDENCE: keine Fills im Fenster — kein handelsnaher Slippage-Nachweis (kein PASS).",
                    {
                        "fills_total": 0,
                        "fills_with_ticker": 0,
                    },
                )
            return (
                True,
                "Keine Fills im Fenster — Slippage-KPIs nicht anwendbar (kein Trades-Drift sichtbar).",
                {
                    "fills_total": 0,
                    "fills_with_ticker": 0,
                },
            )
        if strict:
            return (
                False,
                f"NO_EVIDENCE: {n} Fill(s) ohne Ticker-Referenz — `tsdb.ticker`-Backfill prüfen.",
                {
                    "fills_total": n,
                    "fills_with_ticker": 0,
                    "max_p95_bps": 0,
                    "max_abs_bps": 0,
                },
            )
        return (
            True,
            f"{n} Fill(s) ohne Ticker-Referenz im gleichen Zeitraum — pruefe tsdb.ticker-Backfill.",
            {
                "fills_total": n,
                "fills_with_ticker": 0,
                "max_p95_bps": 0,
                "max_abs_bps": 0,
            },
        )

    bps_sorted = sorted(bps_list)
    n = len(bps_sorted)
    p50 = bps_sorted[n // 2]
    p95i = min(n - 1, max(0, int(math.ceil(0.95 * n) - 1)))
    p95 = bps_sorted[p95i] if n else 0.0
    mx = bps_sorted[-1]
    ok = p95 <= max_p95_bps and mx <= max_abs_bps
    ex = {
        "fills_count_bps": n,
        "p50_bps": round(p50, 2),
        "p95_bps": round(p95, 2),
        "max_bps": round(mx, 2),
        "limits": {
            "max_p95_bps": max_p95_bps,
            "max_abs_bps": max_abs_bps,
        },
    }
    msg = (
        f"Slippage: n={n}, p50={p50:.1f} bps, p95={p95:.1f} bps, max={mx:.1f} bps "
        f"(Grenz: p95<={max_p95_bps}, max<={max_abs_bps})"
    )
    return (ok, msg, ex)


def _check_security_incident_trails(
    conn: Any, since: datetime, now: datetime, strict: bool
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "live", "audit_trails"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.audit_trails` fehlt — Security-Trail nicht prüfbar.",
                [],
            )
        return (True, "live.audit_trails fehlt — Security-Pruefung uebersprungen", [])
    rows = conn.execute(
        """
        SELECT
          audit_trail_id, created_ts, category, action, severity, scope, scope_key
        FROM live.audit_trails
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND (
            action = 'SECURITY_INCIDENT_ATTEMPT'
            OR (category = 'security' AND severity = 'critical')
          )
        ORDER BY created_ts DESC
        LIMIT 200
        """,
        (since, now),
    ).fetchall()
    if not rows:
        return (
            True,
            "Kein SECURITY_INCIDENT / security+critical in live.audit_trails im Fenster.",
            [],
        )
    ex = [
        {
            "audit_trail_id": str(x.get("audit_trail_id")),
            "action": x.get("action"),
            "severity": x.get("severity"),
            "scope": x.get("scope"),
            "created_ts": str(x.get("created_ts"))[:32],
        }
        for x in rows[:20]
    ]
    return (False, f"Security-Incident-Zeilen: {len(rows)} (Stichprobe unten).", ex)


def _check_gateway_5xx_patterns(
    conn: Any, since: datetime, now: datetime, strict: bool
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Erkennt 5xx in gateway_request_audit (detail_json) + grobe Textsignatur in
    service_checks, falls kein typisiertes http_status-JSON vorhanden.
    """
    if not _safe_table(conn, "app", "gateway_request_audit"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `app.gateway_request_audit` fehlt — 5xx-Gate nicht belegt.",
                [],
            )
        return (True, "app.gateway_request_audit fehlt — 5xx-Pruefung teilweise.", [])
    from psycopg import errors as pg_errors

    try:
        rows = conn.execute(
            """
            SELECT id, created_ts, action, path,
                   detail_json::text AS dtxt
            FROM app.gateway_request_audit
            WHERE created_ts >= %s
              AND created_ts <= %s
              AND (
                detail_json->>'http_status' ~ '^5[0-9]{2}$'
                OR (detail_json #>> '{response,status}') ~ '^5[0-9]{2}$'
                OR (detail_json #>> '{upstream,http_status}')::text ~ '^5[0-9]{2}$'
                OR (detail_json #>> '{upstream,status_code}')::text ~ '^5[0-9]{2}$'
                OR detail_json::text ~* '"[a-z_]*status[a-z_]*"\\s*:\\s*5[0-9][0-9]'
              )
            ORDER BY created_ts DESC
            LIMIT 100
            """,
            (since, now),
        ).fetchall()
    except pg_errors.UndefinedTable:
        rows = []

    bad_sc: list[dict[str, Any]] = []
    if _safe_table(conn, "ops", "service_checks"):
        try:
            r2 = conn.execute(
                """
                SELECT service_name, check_type, status, ts, details::text AS dtxt
                FROM ops.service_checks
                WHERE ts >= %s
                  AND ts <= %s
                  AND status = 'fail'
                  AND (
                    details::text ~* '5[0-9][0-9].*error'
                    OR details::text ~* '["'']h?t?t?p?_?status["'']\\s*[:=]\\s*5[0-9][0-9]'
                  )
                ORDER BY ts DESC
                LIMIT 100
                """,
                (since, now),
            ).fetchall()
        except (pg_errors.UndefinedTable, Exception):
            r2 = []
        for b in r2 or ():
            bad_sc.append(
                {
                    "quelle": "ops.service_checks (fail+5xx-Hinweis)",
                    "service_name": b.get("service_name"),
                    "ts": b.get("ts"),
                    "dtxt": (b.get("dtxt") or "")[:400],
                }
            )

    out = [
        {
            "quelle": "gateway_request_audit",
            "id": str(x.get("id")),
            "action": str(x.get("action") or "")[:120],
            "path": str(x.get("path") or "")[:120],
            "ts": str(x.get("created_ts"))[:32],
        }
        for x in (rows or ())[:20]
    ]
    out.extend(bad_sc)

    if not out:
        return (
            True,
            "Keine 5xx-/unaufgefangenen-Gateway-Indizien im Pruef-Fenster.",
            [],
        )

    return (False, f"5xx/Upstream-Indizien: {len(out)} Treffer (Stichprobe).", out[:20])


def _check_critical_audit_trails(
    conn: Any, since: datetime, now: datetime, strict: bool
) -> tuple[bool, str, int]:
    if not _safe_table(conn, "live", "audit_trails"):
        if strict:
            return (False, "NO_EVIDENCE: `live.audit_trails` fehlt.", 0)
        return (True, "live.audit_trails fehlt — Prüfung übersprungen", 0)
    n = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM live.audit_trails
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND severity = 'critical'
          AND coalesce(action, '') <> 'SECURITY_INCIDENT_ATTEMPT'
        """,
        (since, now),
    ).fetchone()
    c = int((n or {}).get("c", 0))
    if c > 0:
        return (False, f"live.audit_trails: {c} critical-Einträge im Fenster", c)
    return (True, "Keine critical-`live.audit_trails` im Fenster", 0)


def _check_reconcile_not_chronic_fail(
    conn: Any, since: datetime, until: datetime, strict: bool, max_fail_ratio: float
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "reconcile_snapshots"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.reconcile_snapshots` fehlt — Reconcile-Health nicht belegbar.",
                {},
            )
        return (True, "live.reconcile_snapshots fehlt — Prüfung übersprungen", {})
    r = conn.execute(
        """
        SELECT status, count(*)::int AS c
        FROM live.reconcile_snapshots
        WHERE created_ts >= %s AND created_ts <= %s
        GROUP BY status
        """,
        (since, until),
    ).fetchall()
    if not r:
        if strict:
            return (
                False,
                "NO_EVIDENCE: keine `reconcile_snapshots` im Fenster — Lauf nicht belegt.",
                {"n": 0},
            )
        return (
            True,
            "Keine Reconcile-Snapshots im Fenster (übersprungen, nicht-strict).",
            {},
        )
    by = {str(x.get("status")): int(x.get("c") or 0) for x in r}
    n_tot = sum(by.values())
    n_fail = by.get("fail", 0)
    ratio = n_fail / n_tot if n_tot else 1.0
    ex = {
        "by_status": by,
        "fail_ratio": round(ratio, 4),
        "max_fail_ratio": max_fail_ratio,
    }
    if ratio > max_fail_ratio:
        return (
            False,
            f"Reconcile: Anteil `fail`={ratio:.2%} (>{max_fail_ratio:.0%}) bei n={n_tot}.",
            ex,
        )
    return (
        True,
        f"Reconcile-Snapshots: n={n_tot}, fail_ratio={ratio:.2%} (Limit {max_fail_ratio:.0%}).",
        ex,
    )


def _check_time_and_decision_volume(
    conn: Any,
    since: datetime,
    until: datetime,
    strict: bool,
    min_decisions: int,
    min_window_coverage_ratio: float,
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "execution_decisions"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.execution_decisions` fehlt — kein Entscheidungs-Audit.",
                {},
            )
        return (True, "execution_decisions fehlt — Prüfung übersprungen", {})
    row = conn.execute(
        """
        SELECT
          count(*)::int AS n,
          min(created_ts) AS tmin,
          max(created_ts) AS tmax
        FROM live.execution_decisions
        WHERE created_ts >= %s AND created_ts <= %s
        """,
        (since, until),
    ).fetchone()
    n = int((row or {}).get("n") or 0)
    tmin, tmax = (row or {}).get("tmin"), (row or {}).get("tmax")
    ex: dict[str, Any] = {
        "decisions_in_window": n,
        "tmin": str(tmin) if tmin else None,
        "tmax": str(tmax) if tmax else None,
    }
    if n < min_decisions:
        if strict:
            return (
                False,
                f"NO_EVIDENCE: nur {n} `execution_decisions` (min. {min_decisions} erwartet) — "
                f"Fenster evtl. zu kurz oder Pipeline inaktiv.",
                ex,
            )
        return (
            True,
            f"Nur n={n} `execution_decisions` im Fenster (strict wuerde min. {min_decisions} fordern).",
            ex,
        )
    if tmin is None or tmax is None:
        return (False, "NO_EVIDENCE: keine Timestamps in execution_decisions.", ex)
    span = (tmax - tmin).total_seconds()
    need = (until - since).total_seconds() * max(0.0, min_window_coverage_ratio)
    if span < need:
        if strict:
            return (
                False,
                f"NO_EVIDENCE: Entscheidungs-Spanne {span/3600:.1f}h < {min_window_coverage_ratio:.0%} des {(until-since).total_seconds()/3600:.0f}h-Fensters — "
                f"keine lückenlose Abdeckung.",
                ex,
            )
        return (
            True,
            f"Hinweis: Spanne nur {span/3600:.1f}h (strict-Ziel {min_window_coverage_ratio:.0%} des Fensters).",
            ex,
        )
    return (
        True,
        f"Entscheidungs-Flow: n={n}, Zeitspanne min..max = {span/3600:.1f}h.",
        ex,
    )


def _check_signal_volume(
    conn: Any, since: datetime, until: datetime, strict: bool, min_signals: int
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "app", "signals_v1"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `app.signals_v1` fehlt — Signal-Engine evtl. älteres Schema.",
                {},
            )
        return (True, "app.signals_v1 fehlt — übersprungen", {})
    from_ms = int(since.timestamp() * 1000)
    to_ms = int(until.timestamp() * 1000)
    r = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM app.signals_v1
        WHERE analysis_ts_ms >= %s AND analysis_ts_ms <= %s
        """,
        (from_ms, to_ms),
    ).fetchone()
    c = int((r or {}).get("c") or 0)
    ex = {"signals_in_window": c, "min_expected": min_signals}
    if c < min_signals:
        if strict:
            return (
                False,
                f"NO_EVIDENCE: {c} Signale in `signals_v1` (min. {min_signals} für Matrix).",
                ex,
            )
        return (
            True,
            f"Signale: {c} (strict wuerde min. {min_signals} verlangen).",
            ex,
        )
    return (True, f"Signale (signals_v1) im Fenster: {c} (>= {min_signals}).", ex)


def _check_no_trade_rate_plausible(
    conn: Any,
    since: datetime,
    until: datetime,
    strict: bool,
    max_no_trade_ratio: float,
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "execution_decisions"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.execution_decisions` fehlt — No-Trade-Rate nicht prüfbar.",
                {},
            )
        return (True, "execution_decisions fehlt — No-Trade-Prüfung übersprungen", {})
    rows = conn.execute(
        """
        SELECT decision_action, decision_reason
        FROM live.execution_decisions
        WHERE created_ts >= %s AND created_ts <= %s
        """,
        (since, until),
    ).fetchall()
    total = len(rows or ())
    if total == 0:
        if strict:
            return (
                False,
                "NO_EVIDENCE: keine execution_decisions im Fenster — No-Trade-Plausibilität nicht belegbar.",
                {"total_decisions": 0},
            )
        return (True, "Keine execution_decisions — No-Trade-Rate übersprungen", {})
    blocked = 0
    outage_like = 0
    for r in rows:
        act = str(r.get("decision_action") or "").lower()
        rea = str(r.get("decision_reason") or "")
        if act == "blocked":
            blocked += 1
            if _OUTAGE_REASON_RE.search(rea):
                outage_like += 1
    ratio = blocked / total if total else 1.0
    outage_ratio = outage_like / blocked if blocked else 0.0
    ex = {
        "total_decisions": total,
        "blocked_decisions": blocked,
        "no_trade_ratio": round(ratio, 4),
        "outage_like_blocked_ratio": round(outage_ratio, 4),
        "max_no_trade_ratio": max_no_trade_ratio,
    }
    if ratio > max_no_trade_ratio:
        return (
            False,
            f"No-Trade-Rate={ratio:.2%} (>{max_no_trade_ratio:.0%}) — Burn-in unplausibel.",
            ex,
        )
    if blocked > 0 and outage_ratio >= 0.8 and strict:
        return (
            False,
            "No-Trade-Blockierungen überwiegend outage-/stale-getrieben (>=80%) — Pipeline-Ausfallverdacht.",
            ex,
        )
    return (
        True,
        f"No-Trade-Rate plausibel: {ratio:.2%} (blocked={blocked}/{total}).",
        ex,
    )


def _check_operator_release_gates_enabled(
    conn: Any, since: datetime, until: datetime, strict: bool
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "reconcile_snapshots"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.reconcile_snapshots` fehlt — Gate-Flags nicht prüfbar.",
                {},
            )
        return (True, "reconcile_snapshots fehlt — Gate-Prüfung übersprungen", {})
    row = conn.execute(
        """
        SELECT details_json
        FROM live.reconcile_snapshots
        WHERE created_ts >= %s AND created_ts <= %s
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (since, until),
    ).fetchone()
    details = (row or {}).get("details_json")
    if not isinstance(details, dict):
        if strict:
            return (
                False,
                "NO_EVIDENCE: details_json in reconcile_snapshots fehlt/kein Objekt.",
                {},
            )
        return (True, "details_json fehlt — Gate-Prüfung übersprungen", {})
    controls = details.get("execution_controls")
    if not isinstance(controls, dict):
        if strict:
            return (
                False,
                "NO_EVIDENCE: details_json.execution_controls fehlt.",
                {},
            )
        return (True, "execution_controls fehlt — Gate-Prüfung übersprungen", {})
    binding = controls.get("live_require_execution_binding")
    operator = controls.get("live_require_operator_release_for_live_open")
    shadow_match = controls.get("require_shadow_match_before_live")
    ex = {
        "live_require_execution_binding": binding,
        "live_require_operator_release_for_live_open": operator,
        "require_shadow_match_before_live": shadow_match,
    }
    missing = [k for k, v in ex.items() if not isinstance(v, bool)]
    if missing:
        if strict:
            return (
                False,
                "NO_EVIDENCE: Gate-Flag(s) fehlen in execution_controls: " + ", ".join(missing),
                ex,
            )
        return (True, "Gate-Flag(s) fehlen (nicht-strict).", ex)
    ok = bool(binding) and bool(operator) and bool(shadow_match)
    if not ok:
        return (
            False,
            "Operator-/Binding-/Shadow-Match-Gates sind nicht vollständig aktiv.",
            ex,
        )
    return (True, "Operator-/Binding-/Shadow-Match-Gates sind aktiv.", ex)


def _check_kill_switch_inactive(
    conn: Any, now: datetime, strict: bool
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "live", "kill_switch_events"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.kill_switch_events` fehlt — Kill-Switch-Audit unbekannt.",
                [],
            )
        return (True, "kill_switch_events fehlt — übersprungen", [])
    rows = conn.execute(
        """
        SELECT DISTINCT ON (scope, scope_key)
          scope, scope_key, is_active, event_type, created_ts, reason
        FROM live.kill_switch_events
        WHERE created_ts <= %s
        ORDER BY scope, scope_key, created_ts DESC
        """,
        (now,),
    ).fetchall()
    bad = [x for x in (rows or ()) if x.get("is_active") is True]
    if bad:
        return (
            False,
            f"Kill-Switch: {len(bad)} Scope(s) mit is_active=true (letzter Zustand).",
            [dict(x) for x in bad[:20]],
        )
    return (
        True,
        "Kein aktiver Kill-Switch (letzter Zustand je scope/scope_key inaktiv).",
        [],
    )


def _check_shadow_live_divergence_block(
    conn: Any, since: datetime, until: datetime, strict: bool, max_mismatch_ratio: float
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "shadow_live_assessments"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.shadow_live_assessments` fehlt — Divergenz-Metrik nicht belegt.",
                {},
            )
        return (True, "shadow_live_assessments fehlt — übersprungen", {})
    r = conn.execute(
        """
        SELECT
          count(*) FILTER (WHERE match_ok = true)::int AS n_ok,
          count(*)::int AS n_all,
          count(*) FILTER (WHERE gate_blocked = true)::int AS n_gate
        FROM live.shadow_live_assessments
        WHERE created_ts >= %s AND created_ts <= %s
        """,
        (since, until),
    ).fetchone()
    n_all = int((r or {}).get("n_all") or 0)
    n_ok = int((r or {}).get("n_ok") or 0)
    n_gate = int((r or {}).get("n_gate") or 0)
    ex = {
        "assessments": n_all,
        "match_ok": n_ok,
        "gate_blocked": n_gate,
    }
    if n_all == 0:
        if strict:
            return (
                False,
                "NO_EVIDENCE: keine `shadow_live_assessments` im Fenster.",
                ex,
            )
        return (True, "Keine Shadow/Live-Assessments im Fenster.", ex)
    mismatch = 1.0 - (n_ok / n_all) if n_all else 1.0
    if mismatch > max_mismatch_ratio:
        return (
            False,
            f"Shadow/Live: mismatch_ratio={mismatch:.2%} (>{max_mismatch_ratio:.0%}).",
            ex,
        )
    return (
        True,
        f"Shadow/Live-Assessments: match_ok={n_ok}/{n_all}, gate_blocked={n_gate}.",
        ex,
    )


def _check_burn_in_runtime_from_reconcile(
    conn: Any, since: datetime, until: datetime, strict: bool
) -> tuple[bool, str, dict[str, Any]]:
    """Liest letzte `reconcile_snapshots` im Fenster: Shadow an, Live-Submits aus."""
    if not _safe_table(conn, "live", "reconcile_snapshots"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `live.reconcile_snapshots` fehlt — Laufzeit-Modus nicht prüfbar.",
                {},
            )
        return (True, "reconcile fehlt — übersprungen", {})
    n_row = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM live.reconcile_snapshots
        WHERE created_ts >= %s AND created_ts <= %s
        """,
        (since, until),
    ).fetchone()
    nc = int((n_row or {}).get("c") or 0)
    if nc == 0:
        if strict:
            return (
                False,
                "NO_EVIDENCE: keine `reconcile_snapshots` im Fenster für Modus-Prüfung.",
                {},
            )
        return (True, "keine Reconcile-Snapshots — übersprungen", {})
    row = conn.execute(
        """
        SELECT
          bool_and(shadow_enabled = true) AS shadow_on,
          bool_and(live_submission_enabled = false) AS live_off,
          bool_and(runtime_mode IN ('shadow', 'paper')) AS mode_ok
        FROM live.reconcile_snapshots
        WHERE created_ts >= %s AND created_ts <= %s
        """,
        (since, until),
    ).fetchone()
    if not row or (row or {}).get("shadow_on") is None:
        if strict:
            return (
                False,
                "NO_EVIDENCE: Reconcile-Aggregat leer/NULL trotz count — Schema prüfen.",
                {},
            )
        return (True, "keine Reconcile-Snapshots — übersprungen", {})
    ex = {k: row.get(k) for k in ("shadow_on", "live_off", "mode_ok")}
    ok = (
        bool(ex.get("shadow_on"))
        and bool(ex.get("live_off"))
        and bool(ex.get("mode_ok"))
    )
    if not ok:
        return (
            False,
            f"Modus-Indiz: shadow_enabled={ex.get('shadow_on')!r}, live_submission_enabled soll false sein: {ex.get('live_off')!r}, "
            f"runtime_mode in shadow/paper: {ex.get('mode_ok')!r} — kein reiner Shadow-Burn-in-Modus sichtbar.",
            ex,
        )
    return (
        True,
        "Reconcile-Indizes: shadow an, live_submission aus, Modus paper/shadow.",
        ex,
    )


def _check_ticker_staleness(
    conn: Any, now: datetime, max_age_sec: int, strict: bool
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "tsdb", "ticker"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `tsdb.ticker` fehlt — Markt-Stale nicht belegt.",
                {},
            )
        return (True, "tsdb.ticker fehlt — übersprungen", {})
    r = conn.execute("SELECT max(ts_ms) AS mx FROM tsdb.ticker").fetchone()
    mx = (r or {}).get("mx")
    if mx is None:
        return (False, "NO_EVIDENCE: tsdb.ticker leer (kein Markt-Datensatz).", {})
    from_ms = int(now.timestamp() * 1000)
    age = (from_ms - int(mx)) / 1000.0
    ex = {
        "ticker_max_ts_ms": int(mx),
        "age_sec": round(age, 1),
        "limit_sec": max_age_sec,
    }
    if age > max_age_sec:
        return (
            False,
            f"Stale: letzter Ticker {age:.0f}s alt (Limit {max_age_sec}s).",
            ex,
        )
    return (True, f"Ticker-Frische: {age:.1f}s seit letztem `tsdb.ticker`-Eintrag.", ex)


def _check_leverage_start_profile(
    conn: Any, since: datetime, until: datetime, strict: bool
) -> tuple[bool, str, dict[str, Any]]:
    if not _safe_table(conn, "live", "execution_decisions"):
        if strict:
            return (
                False,
                "NO_EVIDENCE: `execution_decisions` fehlt — Hebel-Profil nicht prüfbar.",
                {},
            )
        return (True, "übersprungen", {})
    r = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM live.execution_decisions
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND leverage IS NOT NULL
          AND leverage > 7
        """,
        (since, until),
    ).fetchone()
    c = int((r or {}).get("c") or 0)
    ex = {"decisions_leverage_gt_7": c}
    if c > 0:
        if strict:
            return (
                False,
                f"Startprofil: {c} `execution_decisions` mit leverage>7 im Fenster — erwartet 7x-Ramp-Profil (kein >7).",
                ex,
            )
        return (True, f"Warn: {c} Entscheidungen >7x (in strict: FAIL).", ex)
    return (True, "Hebel-Startprofil: kein `leverage`>7 im Prüffenster.", ex)


def _check_critical_as_tuple(
    conn: Any, since: datetime, now: datetime, strict: bool
) -> tuple[bool, str, Any]:
    return _check_critical_audit_trails(conn, since, now, strict)


def _verdict_from_results(
    results: list[tuple[str, bool, str, Any]],
) -> str:
    if any((not o) and ("NO_EVIDENCE:" in (e or "")) for _, o, e, _ in results):
        return "NO_EVIDENCE"
    if all(t[1] for t in results):
        return "PASS"
    return "FAIL"


def _fmt_md(
    *,
    since: datetime,
    until: datetime,
    hours: int,
    results: list[tuple[str, bool, str, Any]],
    overall: bool,
    one_line: str,
    label: str,
    git_sha: str,
) -> str:
    when = until.astimezone(UTC).isoformat()
    ssince = since.astimezone(UTC).isoformat()
    if label == "PASS":
        verdict = "**[PASS / GO]**"
    elif label == "NO_EVIDENCE":
        verdict = "**[NO_EVIDENCE]**"
    else:
        verdict = "**[NO-GO / FAIL]**"
    lines: list[str] = [
        "# READINESS_EVIDENCE — Shadow-Burn-in (Audit-Nachweis)",
        "",
        f"## Entscheidung: {verdict} — `{label}`  ",
        f"- **git_sha (Repo/CI):** `{git_sha}`  ",
        "",
        f"- **Zeitfenster:** letzte {hours}h, Ende (UTC) `{when}`  ",
        f"- **Fensterstart (UTC):** `{ssince}`  ",
        "",
    ]
    for name, ok, expl, extra in results:
        if ok:
            status = "OK"
        elif "NO_EVIDENCE:" in expl:
            status = "NO_EVIDENCE"
        else:
            status = "FAIL"
        lines.append(f"## {name} — {status}")
        lines.append("")
        lines.append(expl)
        lines.append("")
        if extra and isinstance(extra, list) and extra:
            try:
                sample = [
                    redact_nested_mapping(x) if isinstance(x, dict) else x
                    for x in extra[:20]
                ]
            except (TypeError, ValueError, KeyError):
                sample = extra[:20]
            lines.append("```json")
            lines.append(json.dumps(sample, ensure_ascii=False, default=str)[:10_000])
            lines.append("```")
        elif extra and isinstance(extra, dict) and extra:
            lines.append("```json")
            lines.append(
                json.dumps(
                    redact_nested_mapping(extra) if isinstance(extra, dict) else extra,
                    ensure_ascii=False,
                    default=str,
                )[:10_000]
            )
            lines.append("```")
            lines.append("")
        elif extra and not isinstance(extra, list | dict):
            lines.append(f"_{extra}_")
            lines.append("")
    lines.append("---")
    lines.append("")
    if overall:
        lines.append("## " + verdict.replace("**", "") + " (Gates)  ")
    else:
        lines.append("## " + one_line)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Readiness- / Shadow-Burn-in Zertifikat: Markdown/JSON, PASS/NO_EVIDENCE/FAIL.",
    )
    ap.add_argument(
        "--hours",
        type=int,
        default=72,
        help="Rueckblick in Stunden (default 72; fuer Zertifikat 72+ empfohlen).",
    )
    ap.add_argument("--env-file", type=Path, default=None, help="liest DATABASE_URL=…")
    ap.add_argument(
        "--database-url",
        default="",
        help="DSN; Default: $DATABASE_URL; sonst --env-file.",
    )
    ap.add_argument(
        "--max-pipeline-lag-ms",
        type=int,
        default=5000,
        help="stream_checks / service_checks Latenz (default 5000).",
    )
    ap.add_argument(
        "--max-heartbeat-gap-sec",
        type=int,
        default=600,
        help="Max. Luecke `health` je service_name (s).",
    )
    ap.add_argument(
        "--max-slippage-p95-bps",
        type=float,
        default=50.0,
    )
    ap.add_argument(
        "--max-slippage-peak-bps",
        type=float,
        default=200.0,
    )
    ap.add_argument(
        "--min-decisions",
        type=int,
        default=3,
        help="Min. live.execution_decisions im Fenster (strict).",
    )
    ap.add_argument(
        "--min-signals",
        type=int,
        default=2,
        help="Min. app.signals_v1 im Fenster (strict).",
    )
    ap.add_argument(
        "--min-window-coverage-ratio",
        type=float,
        default=0.95,
        help="Mindestabdeckung von execution_decisions tmin..tmax im Fenster (strict, default 0.95).",
    )
    ap.add_argument(
        "--max-no-trade-ratio",
        type=float,
        default=0.95,
        help="Maximaler Anteil blocked/no-trade in execution_decisions (strict, default 0.95).",
    )
    ap.add_argument(
        "--max-reconcile-fail-ratio",
        type=float,
        default=0.2,
        help="Anteil fail-Snapshots (strict, default 0.2).",
    )
    ap.add_argument(
        "--max-ticker-stale-sec",
        type=int,
        default=300,
        help="Max. Alter `tsdb.ticker` in Sekunden (default 300).",
    )
    ap.add_argument(
        "--max-shadow-mismatch-ratio",
        type=float,
        default=0.05,
        help="Anteil nicht match_ok in shadow_live_assessments (default 0.05).",
    )
    ap.add_argument(
        "--readiness-out",
        type=Path,
        default=_DEFAULT_READINESS,
        help=f"Markdown (default: {_DEFAULT_READINESS}).",
    )
    ap.add_argument(
        "--no-readiness-file",
        action="store_true",
    )
    ap.add_argument(
        "--output-md",
        type=Path,
        default=None,
        dest="outmd",
        help="ueberschreibt --readiness-out wenn gesetzt.",
    )
    ap.add_argument("--output-json", type=Path, default=None, dest="outjson")
    ap.add_argument("--dry-run", action="store_true", help="Kein DB-Zugriff; erzeugt sicheren Beispiel-/Warnreport.")
    ap.add_argument("--input-json", type=Path, default=None, help="Fixture-basierte Burn-in-Bewertung ohne DB.")
    ap.add_argument("--certificate-json", type=Path, default=None, help="Externer Shadow-Burn-in-Certificate-Contract ohne DB.")
    ap.add_argument("--write-certificate-template", type=Path, default=None, help="Schreibt ein secret-freies Certificate-Template.")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fehlende/ leere Kernevidence -> NO_EVIDENCE (Exitcde 2), kein stilles PASS.",
    )
    args = ap.parse_args()
    if args.write_certificate_template is not None:
        args.write_certificate_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_certificate_template.write_text(
            json.dumps(build_shadow_certificate_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_certificate_template}")
        return 0
    if args.certificate_json is not None:
        loaded = json.loads(args.certificate_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Certificate root muss ein JSON-Objekt sein.")
        status, blockers, warnings = assess_shadow_certificate(loaded)
        secret_issues = certificate_secret_surface_issues(loaded)
        payload = {
            "ok": status == "PASS" and not secret_issues,
            "status": status,
            "blockers": blockers + secret_issues,
            "warnings": warnings,
        }
        if args.outmd is not None:
            args.outmd.parent.mkdir(parents=True, exist_ok=True)
            args.outmd.write_text(
                _certificate_markdown(loaded, status, blockers, warnings, secret_issues),
                encoding="utf-8",
            )
        if args.outjson is not None:
            args.outjson.parent.mkdir(parents=True, exist_ok=True)
            args.outjson.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        print(_certificate_markdown(loaded, status, blockers, warnings, secret_issues), end="")
        return 1 if args.strict and not payload["ok"] else 0
    if args.dry_run or args.input_json is not None:
        return _run_fixture_or_dry_run(
            input_json=args.input_json,
            output_md=args.outmd,
            dry_run=bool(args.dry_run),
        )
    dsn = (args.database_url or os.environ.get("DATABASE_URL") or "").strip() or None
    if args.env_file and args.env_file.is_file() and dsn is None:
        dsn = _read_env_dsn(args.env_file, "DATABASE_URL")

    until = datetime.now(UTC)
    h = max(1, int(args.hours))
    since = until - timedelta(hours=h)
    from_ms = int(since.timestamp() * 1000)
    to_ms = int(until.timestamp() * 1000)
    st = bool(args.strict)
    out_path: Path = args.readiness_out
    if args.outmd is not None:
        out_path = args.outmd
    results: list[tuple[str, bool, str, Any]] = []
    first_fail = ""
    gsha = _git_sha()

    if not dsn:
        results = [
            (
                "0) Datenquelle (DATABASE_URL) [strict]",
                False,
                "NO_EVIDENCE: kein DSN. --database-url, DATABASE_URL oder --env-file mit DATABASE_URL.",
                {},
            )
        ]
        label = _verdict_from_results(results)
        body = _fmt_md(
            since=since,
            until=until,
            hours=h,
            results=results,
            overall=False,
            one_line="**Ergebnis: NO_EVIDENCE** — keine Datenquelle",
            label=label,
            git_sha=gsha,
        )
        r_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        payload = {
            "verdict": label,
            "strict": st,
            "git_sha": gsha,
            "report_sha256": r_sha,
            "hours": h,
            "window_utc": {
                "start": since.astimezone(UTC).isoformat(),
                "end": until.astimezone(UTC).isoformat(),
            },
            "checks": [
                {
                    "name": results[0][0],
                    "ok": False,
                    "message": results[0][2],
                    "no_evidence": True,
                }
            ],
        }
        print(body, end="")
        if not args.no_readiness_file:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(body, encoding="utf-8")
            print(f"\nWritten: {out_path}", file=sys.stderr)
        if args.outjson:
            args.outjson.parent.mkdir(parents=True, exist_ok=True)
            args.outjson.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Written: {args.outjson}", file=sys.stderr)
        print(
            "\n[NO_EVIDENCE] kein DSN — Burn-in kann ohne Datenquelle nicht bewertet werden.\n",
            file=sys.stderr,
        )
        return 2

    def _b(name: str, res: tuple[bool, str, Any]) -> None:
        nonlocal first_fail
        ok, expl, ex = res
        results.append((name, ok, expl, ex))
        if not ok:
            first_fail = first_fail or (expl[:200] if expl else name)

    with _connect(dsn) as conn:
        _b(
            "0) Volumen & Abdeckung (Entscheidungen, Zeitspanne, Signale) [strict]",
            _check_time_and_decision_volume(
                conn,
                since,
                until,
                st,
                int(args.min_decisions),
                float(args.min_window_coverage_ratio),
            ),
        )
        _b(
            "0b) app.signals_v1 Volumen [strict]",
            _check_signal_volume(conn, since, until, st, int(args.min_signals)),
        )
        _b(
            "0c) Reconcile-Snapshots (chron. fail) [strict]",
            _check_reconcile_not_chronic_fail(
                conn, since, until, st, float(args.max_reconcile_fail_ratio)
            ),
        )
        _b(
            "0d) Laufzeit-Indiz: shadow on, live submit off (reconcile_snapshots) [strict]",
            _check_burn_in_runtime_from_reconcile(conn, since, until, st),
        )
        _b(
            "0e) tsdb.ticker Stale [strict]",
            _check_ticker_staleness(conn, until, int(args.max_ticker_stale_sec), st),
        )
        _b(
            "0f) Shadow/Live-Assessments (Divergenz) [strict]",
            _check_shadow_live_divergence_block(
                conn, since, until, st, float(args.max_shadow_mismatch_ratio)
            ),
        )
        _b(
            "0f2) Operator-/Binding-/Shadow-Match-Gates aktiv [strict]",
            _check_operator_release_gates_enabled(conn, since, until, st),
        )
        _b(
            "0f3) No-Trade-Rate plausibel (kein Pipeline-Ausfallmuster) [strict]",
            _check_no_trade_rate_plausible(
                conn, since, until, st, float(args.max_no_trade_ratio)
            ),
        )
        _b(
            "0g) Hebel 7x-Start (kein >7) [strict]",
            _check_leverage_start_profile(conn, since, until, st),
        )
        _b("0h) Kill-Switch inaktiv", _check_kill_switch_inactive(conn, until, st))
        _b(
            "1) Heartbeats (ops.service_checks health)",
            _check_heartbeat_gaps(conn, since, until, args.max_heartbeat_gap_sec, st),
        )
        _b(
            f"2) Slippage: paper.fills vs. tsdb.ticker (p95<={args.max_slippage_p95_bps} "
            f"max<={args.max_slippage_peak_bps} bps) [strict]",
            _check_paper_slippage_bps(
                conn,
                from_ms,
                to_ms,
                args.max_slippage_p95_bps,
                args.max_slippage_peak_bps,
                st,
            ),
        )
        _b(
            "3) Security-Incidents (live.audit_trails)",
            _check_security_incident_trails(conn, since, until, st),
        )
        _b(
            "4) 5xx / Upstream (gateway, service_checks)",
            _check_gateway_5xx_patterns(conn, since, until, st),
        )
        _b(
            "5) live.audit_trails (critical)",
            _check_critical_as_tuple(conn, since, until, st),
        )
        _b(
            "6) execution_decisions: Fat-Finger- blocked",
            _check_suspicious_blocks(conn, since, until, st),
        )
        _b(
            "7) paper.strategy_events: AUTO_BLOCKED",
            _check_paper_auto_blocked(conn, since, until, st),
        )
        _b(
            "8) ops.alerts (warn/critical, offen)",
            _check_alerts(conn, since, until, st),
        )
        _b(
            "9) Stream-/Service-Latenz",
            _check_stream_and_service_lag(
                conn, since, until, args.max_pipeline_lag_ms, st
            ),
        )
    label = _verdict_from_results(results)
    one_line = f"**Ergebnis: {label}** — {first_fail} — {until.isoformat()}"
    body = _fmt_md(
        since=since,
        until=until,
        hours=h,
        results=results,
        overall=(label == "PASS"),
        one_line=one_line,
        label=label,
        git_sha=gsha,
    )
    h_body = hashlib.sha256(body.encode("utf-8"))
    r_sha = h_body.hexdigest()
    payload = {
        "verdict": label,
        "strict": st,
        "git_sha": gsha,
        "report_sha256": r_sha,
        "hours": h,
        "window_utc": {
            "start": since.astimezone(UTC).isoformat(),
            "end": until.astimezone(UTC).isoformat(),
        },
        "checks": [
            {
                "name": n,
                "ok": ok,
                "message": e,
                "no_evidence": (not ok) and ("NO_EVIDENCE:" in (e or "")),
            }
            for n, ok, e, _x in results
        ],
    }
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError, TypeError):
            pass
    print(body, end="")
    if not args.no_readiness_file:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(f"\nWritten: {out_path}", file=sys.stderr)
    if args.outjson:
        args.outjson.parent.mkdir(parents=True, exist_ok=True)
        args.outjson.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Written: {args.outjson}", file=sys.stderr)

    if label == "PASS":
        print(
            f"\n[PASS/GO] {h}h — Evidenz: {out_path!s}\n",
            file=sys.stderr,
        )
        return 0
    if label == "NO_EVIDENCE":
        print(
            f"\n[NO_EVIDENCE] strict/fehlende Daten — {out_path!s} / siehe JSON\n{first_fail}\n",
            file=sys.stderr,
        )
        return 2
    print(
        f"\n[NO-GO/FAIL] {out_path!s}\n{first_fail}\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
