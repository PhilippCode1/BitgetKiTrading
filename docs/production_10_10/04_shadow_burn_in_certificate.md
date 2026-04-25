# Shadow-Burn-in-Zertifikat (72h+ Evidenz)

Vorgeschrieben: `docs/shadow_burn_in_ramp.md`, Launch-Checkliste, Gap-Register.

## Werkzeug

- `scripts/verify_shadow_burn_in.py` — bewertet **Postgres-Tabellen** im Rückblickfenster (default 72h).
- Ausgabe: **Markdown** (stdout / `--output-md` / `--readiness-out`) und optional **JSON** (`--output-json`) inkl. `verdict` (`PASS` / `FAIL` / `NO_EVIDENCE`), `git_sha`, `report_sha256` (SHA-256 des **Markdown-Textes** der Konsole, nicht des Dateisystems-Zufalls), `window_utc`, `checks[]`.

## Exitcodes

| Code | Bedeutung |
|------|-----------|
| 0 | `verdict: PASS` — alle geprüften harten Gates bestanden. |
| 1 | `verdict: FAIL` — harter Prüf-Fail (z. B. offene critical-Alerts, Reconcile-Dominanz `fail`, Slippage, …). |
| 2 | `verdict: NO_EVIDENCE` — typisch mit **`--strict`**: fehlende Schema-Fläche oder leere Kerndaten; **kein** stilles Grün. |
| 1 (vor DB) | Kein DSN; Verbindung nicht möglich. |

**Ohne laufendes, befülltes Schema** liefert `--strict` faktisch `NO_EVIDENCE` (Exit 2) statt fälschlich `PASS` durch “übersprungene” Checks.

## Kriterien (Kurz)

- **Volumen / Abdeckung:** Mindestzahlen an `live.execution_decisions` und `app.signals_v1` plus Mindest-Fensterabdeckung (`--min-window-coverage-ratio`, strict).
- **Reconcile:** Anteil `status=fail` in `live.reconcile_snapshots` unter Schranke; Modus aus Snapshots: shadow an, `live_submission_enabled` aus, `runtime_mode` in shadow/paper.
- **Divergenz:** `live.shadow_live_assessments` — Mismatch-Quote; bei 0 Zeilen in strict → NO_EVIDENCE.
- **Operator-Live-Gates:** aus `reconcile_snapshots.details_json.execution_controls` müssen
  `live_require_execution_binding=true`, `live_require_operator_release_for_live_open=true`
  und `require_shadow_match_before_live=true` hervorgehen; fehlende Flags sind in strict `NO_EVIDENCE`.
- **Kill-Switch:** `live.kill_switch_events` — letzter Zustand je (scope, scope_key) mit `is_active` darf nicht “offen” sein in der geprüften Sicht.
- **Ticker-Frische:** `max(ts_ms)` in `tsdb.ticker` vs. “jetzt”.
- **Hebel:** Keine `execution_decisions` mit `leverage` > 7 im Fenster (7x-Start-Ramp-Indiz).
- **No-Trade-Plausibilität:** `blocked`-Quote bleibt unter `--max-no-trade-ratio`; starke outage-/stale-dominierte Blockierungen führen in strict zu FAIL.
- **Bisherige** Gates: Heartbeats, Slippage, Security/5xx, Alerts, Stream/Service.

## Nicht vollständig in SQL abbildbar (Ergänzung nötig / extern)

- **Vollständige 14-Tage- / 3-Session-Cluster-** Matrix laut `shadow_burn_in_ramp.md` (Skript prüft Zeitspanne/Counts als Proxy, keine Kalender-Session-Cluster-Analyse).
- **ENV-Gleichheit** mit `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false` usw. unmittelbar aus Tabelle: nur indirekt über `reconcile_snapshots`; **Voll-Abgleich** mit Deployment-Secret-Store = Operator-Nachweis, nicht ersetzbar aus reinem SQL-Gap im Tool.
- **“Operator-Release-Gates”** in Sinne von *jedem* Live-Submit: nur teilweise über `live.execution_operator_releases` / Journals ableitbar; vollständige Beweiskette wäre zusätzliches Report-Feld/Tool-Upgrade.

## Staging-Ablauf

1. `DATABASE_URL` in Shell/Secret, nicht in Git.
2. `python scripts/verify_shadow_burn_in.py --hours 72 --strict --output-md reports/sbi.md --output-json reports/sbi.json`
3. JSON und Markdown in Release-Archiv; **Signoff** referenziert `report_sha256` und Durchführungszeit.
4. Für Live-Mirror: siehe Launch-Checkliste (archivierter Report mit `PASS` und SHA-Referenz).
