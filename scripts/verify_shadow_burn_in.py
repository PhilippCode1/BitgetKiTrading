#!/usr/bin/env python3
"""
Shadow-Burn-in Auswertung: Postgres + Ops-Metriken, Markdown-Zertifikat (stdout, optional Datei).

Prüft im Zeitfenster u.a.:
- abgelehnte / risk-blockierte Pfade (keine Fat-Finger-Muster in live.execution_decisions)
- offene P0/P1-äquivalente Alerts (ops.alerts: critical, warn)
- Stream-/Service-Latenz (lag/latency_ms > Schwelle)
- Lücken in Heartbeats (ops.service_checks — max. Abstand zwischen Prüfungen)

Umgebung: DATABASE_URL (postgresql://…)

    python scripts/verify_shadow_burn_in.py --hours 72
    python scripts/verify_shadow_burn_in.py --hours 168 --output-md /tmp/burn_in.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


@contextmanager
def _connect(
    dsn: str,
):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        raise SystemExit("psycopg fehlt — pip install psycopg[binary] bzw. requirements") from e
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


def _check_suspicious_blocks(
    conn: Any, since: datetime, until: datetime
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Gibt (ok, summary, beispielzeilen) — ok=False bei Verdacht auf Fehlbedienung/Engine-Fat-Finger."""
    if not _safe_table(conn, "live", "execution_decisions"):
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
        blob = f"{reason} {pjson}"
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
    conn: Any, since: datetime, until: datetime
) -> tuple[bool, str, int]:
    if not _safe_table(conn, "paper", "strategy_events"):
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
    msg = (
        f"AUTO_BLOCKED-Paper-Events: {c} (erwartet bei Gates; kein autonomer Fail ohne muster). "
    )
    return (ok, msg, c)


def _check_alerts(
    conn: Any, since: datetime, now: datetime
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "ops", "alerts"):
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
        return (True, "Keine offenen P0/P1-äquivalenten Alerts (warn/critical) im Fenster.", [])
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
) -> tuple[bool, str, list[dict[str, Any]]]:
    from psycopg import errors as pg_errors

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
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "ops", "service_checks"):
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
            f"Health-Check-Lücken ≤ {max_gap_sec}s je Service (Partition health).",
            rows,
        )
    return (False, f"Heartbeat: max_gap > {max_gap_sec}s bei Dienst(en)", problems)


def _check_critical_audit_trails(
    conn: Any, since: datetime, now: datetime
) -> tuple[bool, str, int]:
    if not _safe_table(conn, "live", "audit_trails"):
        return (True, "live.audit_trails fehlt — Prüfung übersprungen", 0)
    n = conn.execute(
        """
        SELECT count(*)::int AS c
        FROM live.audit_trails
        WHERE created_ts >= %s
          AND created_ts <= %s
          AND severity = 'critical'
        """,
        (since, now),
    ).fetchone()
    c = int((n or {}).get("c", 0))
    if c > 0:
        return (False, f"live.audit_trails: {c} critical-Einträge im Fenster", c)
    return (True, "Keine critical-`live.audit_trails` im Fenster", 0)


def _fmt_md(
    *,
    since: datetime,
    until: datetime,
    hours: int,
    results: list[tuple[str, bool, str, Any]],
    overall: bool,
    one_line: str,
) -> str:
    when = until.astimezone(UTC).isoformat()
    ssince = since.astimezone(UTC).isoformat()
    lines: list[str] = [
        "# Shadow-Burn-in Zertifikat (datenbasiert)",
        "",
        f"- **Zeitfenster:** {hours}h bis `{when}`  ",
        f"- **Start (UTC):** `{ssince}`  ",
        "",
    ]
    for name, ok, expl, extra in results:
        status = "OK" if ok else "FAIL"
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
            lines.append(
                json.dumps(sample, ensure_ascii=False, default=str)[:10_000]
            )
            lines.append("```")
        elif extra and not isinstance(extra, (list, dict)):
            lines.append(f"_{extra}_")
            lines.append("")
    lines.append("---")
    lines.append("")
    if overall:
        lines.append(
            f"## **[PASS]** {hours} Stunden Shadow-Mode ohne "
            f"kritische Abbrüche (automatisierte Kriterien erfüllt) — {when}  "
        )
    else:
        lines.append("## " + one_line)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Postgres-basiertes Shadow-Burn-in Zertifikat (Markdown).",
    )
    ap.add_argument(
        "--hours",
        type=int,
        default=72,
        help="Rückblick in Stunden (default 72).",
    )
    ap.add_argument(
        "--database-url",
        default=(os.environ.get("DATABASE_URL") or "").strip(),
        help="Default: $DATABASE_URL",
    )
    ap.add_argument(
        "--max-pipeline-lag-ms",
        type=int,
        default=5000,
        help="Schwelle stream_checks.lag / service_checks.latency_ms (default 5000).",
    )
    ap.add_argument(
        "--max-heartbeat-gap-sec",
        type=int,
        default=600,
        help="Max. erlaubte Lücke zwischen health-checks derselben service_name (s).",
    )
    ap.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Optional: Markdown-Report auch in Datei schreiben.",
    )
    args = ap.parse_args()
    dsn = args.database_url
    if not dsn:
        print(
            "ERROR: DATABASE_URL leer. Setze Umgebungsvariable "
            "oder --database-url.",
            file=sys.stderr,
        )
        return 1

    until = datetime.now(UTC)
    since = until - timedelta(hours=max(1, int(args.hours)))
    results: list[tuple[str, bool, str, Any]] = []
    all_ok = True
    first_fail = ""

    with _connect(dsn) as conn:
        ok, expl, ex = _check_suspicious_blocks(conn, since, until)
        results.append(("1) Fat-Finger / abgelehnte Orders (live.execution_decisions)", ok, expl, ex))
        if not ok:
            all_ok = False
            first_fail = first_fail or f"Verdächtig blockiert: {expl}"

        ok2, expl2, c = _check_paper_auto_blocked(conn, since, until)
        results.append(
            (f"2) Paper strategy AUTO_BLOCKED (n={c}) — Hinweis", True, expl2, c),
        )

        ok, expl, ex = _check_alerts(conn, since, until)
        results.append(("3) P0/P1-äquivalent: offene ops.alerts (warn/critical)", ok, expl, ex))
        if not ok:
            all_ok = False
            a0 = ex[0] if ex else {}
            ts = a0.get("created_ts", "")
            first_fail = first_fail or f"Alert {a0.get('alert_key', '?')} @ {ts}"

        ok, expl, ex = _check_stream_and_service_lag(
            conn, since, until, args.max_pipeline_lag_ms
        )
        results.append(
            (
                "4) Pipeline: Stream-/Service (lag/latency_ms, fail-Status)",
                ok,
                expl,
                ex,
            )
        )
        if not ok:
            all_ok = False
            first_fail = first_fail or f"Pipeline-Lag/ fail: {expl}"

        ok, expl, ex = _check_heartbeat_gaps(
            conn, since, until, args.max_heartbeat_gap_sec
        )
        q = "5) Heartbeat: ops.service_checks (health) max gap"
        results.append((f"{q} ≤ {args.max_heartbeat_gap_sec}s", ok, expl, ex))
        if not ok:
            all_ok = False
            first_fail = first_fail or f"Heartbeat: {expl}"

        ok, expl, c = _check_critical_audit_trails(conn, since, until)
        results.append(("6) live.audit_trails critical", ok, expl, c))
        if not ok:
            all_ok = False
            first_fail = first_fail or f"Kritische Audits: {c}"

    one_line_fail = (
        f"**[FAIL]** {first_fail} — {until.isoformat()}"
    )
    body = _fmt_md(
        since=since,
        until=until,
        hours=int(args.hours),
        results=results,
        overall=all_ok,
        one_line=one_line_fail,
    )
    print(body, end="")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(body, encoding="utf-8")
        print(f"\n# Geschrieben: {args.output_md}", file=sys.stderr)
    if not all_ok:
        one = one_line_fail.replace("**[FAIL]**", "[FAIL]", 1).replace("**", "")
        print(
            f"\n{one}",
            file=sys.stderr,
        )
        return 1
    print(
        f"\n[PASS] {args.hours} Stunden Shadow-Mode ohne kritische Abbrüche absolviert "
        f"(Kriterien laut Skript) — {until.isoformat()}\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
