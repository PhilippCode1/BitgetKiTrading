#!/usr/bin/env python3
"""
Shadow-Burn-in / Readiness-Zertifikat: datenbasiertes GO/NO-GO (Postgres, Markdown).

Harte KPI-Cluster:
- Lückenlose Herzfrequenz-Proxys: `ops.service_checks` (check_type=health) max. Lücke je Service
- Slippage: `paper.fills` vs. Referenz-`tsdb.ticker` (letzter Mark/Last <= Fill-Zeit) in bps
- Sicherheits-Incidents: `live.audit_trails` (`SECURITY_INCIDENT_ATTEMPT` / security+critical)
- 5xx-/Upstream-Fehler: u.a. `app.gateway_request_audit` (detail_json http/upstream-Status) +
  (legacy) kritischer Härte-Check: `ops.service_checks` fail in Kombination mit 5xx-Hinweis
- Ergänzend: blockierte live-Entscheidungen, Alerts, Stream-Lag, paper AUTO_BLOCKED, …

Output: stdout + `READINESS_EVIDENCE.md` (Repo-Root) oder `--readiness-out` / `--output-md`

    python scripts/verify_shadow_burn_in.py --hours 72
    python scripts/verify_shadow_burn_in.py --hours 168 --readiness-out /tmp/READINESS_EVIDENCE.md
"""

from __future__ import annotations

import argparse
import json
import math
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

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_READINESS = _REPO / "READINESS_EVIDENCE.md"


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
) -> tuple[bool, str, dict[str, Any]]:
    """
    Fills vs. zuletzt bekannten Ticker (Mark/Last) vor fill.ts_ms. Ohne Ticker-Referenz
    zählt die Zeile nicht für Slippage-Statistik.
    """
    if not all(
        _safe_table(conn, s, t)
        for s, t in (("paper", "fills"), ("paper", "positions"), ("tsdb", "ticker"))
    ):
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
            return (
                True,
                "Keine Fills im Fenster — Slippage-KPIs nicht anwendbar (kein Trades-Drift sichtbar).",
                {
                    "fills_total": 0,
                    "fills_with_ticker": 0,
                },
            )
        return (
            True,
            f"{n} Fill(s) ohne Ticker-Referenz im gleichen Zeitraum — pruefe tsdb.ticker-Backfill.",
            {"fills_total": n, "fills_with_ticker": 0, "max_p95_bps": 0, "max_abs_bps": 0},
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
    conn: Any, since: datetime, now: datetime
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not _safe_table(conn, "live", "audit_trails"):
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
    conn: Any, since: datetime, now: datetime
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Erkennt 5xx in gateway_request_audit (detail_json) + grobe Textsignatur in
    service_checks, falls kein typisiertes http_status-JSON vorhanden.
    """
    if not _safe_table(conn, "app", "gateway_request_audit"):
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
        return (True, "Keine 5xx-/unaufgefangenen-Gateway-Indizien im Pruef-Fenster.", [])

    return (False, f"5xx/Upstream-Indizien: {len(out)} Treffer (Stichprobe).", out[:20])


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
          AND coalesce(action, '') <> 'SECURITY_INCIDENT_ATTEMPT'
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
    verdict = "**[GO]**" if overall else "**[NO-GO]**"
    lines: list[str] = [
        "# READINESS_EVIDENCE — Shadow-Burn-in (Audit-Nachweis)",
        "",
        f"## Entscheidung: {verdict} (KPI-Blöcke unten, alle harten Gates muessen `OK` sein).",
        "",
        f"- **Zeitfenster:** letzte {hours}h, Ende (UTC) `{when}`  ",
        f"- **Fensterstart (UTC):** `{ssince}`  ",
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
        lines.append("## " + verdict.replace("**", "") + " (alle Gate-Checks bestanden)  ")
    else:
        lines.append("## " + one_line)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Readiness- / Shadow-Burn-in Zertifikat: READINESS_EVIDENCE.md, [GO]/[NO-GO].",
    )
    ap.add_argument(
        "--hours",
        type=int,
        default=72,
        help="Rueckblick in Stunden (default 72).",
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
        help="Max. erlaubte Luecke health-checks je service_name (s, ops.service_checks).",
    )
    ap.add_argument(
        "--max-slippage-p95-bps",
        type=float,
        default=50.0,
        help="GO wenn Slippage-p95 bps <= dieser Wert (Fills vs. Ticker, default 50).",
    )
    ap.add_argument(
        "--max-slippage-peak-bps",
        type=float,
        default=200.0,
        help="GO wenn max. Slippage (bps) <= dieser Wert (default 200).",
    )
    ap.add_argument(
        "--readiness-out",
        type=Path,
        default=_DEFAULT_READINESS,
        help=f"Markdown-Report (default: {_DEFAULT_READINESS.name} im Repo-Root).",
    )
    ap.add_argument(
        "--no-readiness-file",
        action="store_true",
        help="Nicht nach Datei schreiben (nur stdout / Exitcode).",
    )
    ap.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Alias: ueberschreibt --readiness-out wenn gesetzt (Legacy).",
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
    h = max(1, int(args.hours))
    since = until - timedelta(hours=h)
    from_ms = int(since.timestamp() * 1000)
    to_ms = int(until.timestamp() * 1000)
    out_path: Path = args.readiness_out
    if args.output_md is not None:
        out_path = args.output_md
    results: list[tuple[str, bool, str, Any]] = []
    all_ok = True
    first_fail = ""

    def _b(name: str, res: tuple[bool, str, Any], *, must: bool = True) -> None:
        nonlocal all_ok, first_fail
        ok, expl, ex = res
        results.append((name, ok, expl, ex))
        if must and (not ok):
            all_ok = False
            first_fail = first_fail or (expl[:200] if expl else name)

    with _connect(dsn) as conn:
        _b(
            "1) Lueckenlose Service-Pruefungen (Heartbeats, ops.service_checks health)",
            _check_heartbeat_gaps(conn, since, until, args.max_heartbeat_gap_sec),
        )
        _b(
            f"2) Slippage: paper.fills vs. tsdb.ticker (p95<={args.max_slippage_p95_bps} "
            f"max<={args.max_slippage_peak_bps} bps)",
            _check_paper_slippage_bps(
                conn,
                from_ms,
                to_ms,
                args.max_slippage_p95_bps,
                args.max_slippage_peak_bps,
            ),
        )
        _b(
            "3) Security-Incidents (live.audit_trails: SECURITY_INCIDENT / security+critical)",
            _check_security_incident_trails(conn, since, until),
        )
        _b(
            "4) 5xx / unaufgefangene Upstream-Fehler (gateway_request_audit, services_checks)",
            _check_gateway_5xx_patterns(conn, since, until),
        )
        _b(
            "5) Weitere live.audit_trails (critical, o. security-Einzelzeilen)",
            _check_critical_as_tuple(conn, since, until),
        )
        _b(
            "6) Abgelehnte Orders: Fat-Finger-/Betragsverdacht (live.execution_decisions blocked)",
            _check_suspicious_blocks(conn, since, until),
        )
        ok_pb, ex_pb, n_pb = _check_paper_auto_blocked(conn, since, until)
        results.append(
            (f"7) Paper: AUTO_BLOCKED (Hinweis) n={n_pb}", True, ex_pb, n_pb)
        )
        _b(
            "8) ops.alerts offen (warn/critical) im Fenster",
            _check_alerts(conn, since, until),
        )
        _b(
            "9) Stream-/Service-Latenz (lag, latency, fail)",
            _check_stream_and_service_lag(
                conn, since, until, args.max_pipeline_lag_ms
            ),
        )
    one_line_fail = f"**[NO-GO]** {first_fail} — {until.isoformat()}"
    body = _fmt_md(
        since=since,
        until=until,
        hours=h,
        results=results,
        overall=all_ok,
        one_line=one_line_fail,
    )
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError, TypeError):
            pass
    print(body, end="")
    if not args.no_readiness_file:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(
            f"\nWritten: {out_path}",
            file=sys.stderr,
        )
    if not all_ok:
        print(
            f"\n[NO-GO] Burn-in/Readiness — siehe {out_path!s}\n{first_fail}\n",
            file=sys.stderr,
        )
        return 1
    print(
        f"\n[GO] {h}h Fenster: alle harten Gates bestanden. Evidenz: {out_path!s}\n",
        file=sys.stderr,
    )
    return 0


def _check_critical_as_tuple(
    conn: Any, since: datetime, now: datetime
) -> tuple[bool, str, Any]:
    return _check_critical_audit_trails(conn, since, now)


if __name__ == "__main__":
    raise SystemExit(main())
