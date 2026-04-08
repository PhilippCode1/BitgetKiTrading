# Dashboard als Operator-Konsole

Dieses Dokument beschreibt das Next.js-Dashboard als **Betriebswerkzeug**, nicht als Marketing-Oberfläche.

Kanonische Statussprache: `docs/operator_status_language.md`.

## Hauptansichten

| Pfad                         | Zweck                                                                                                                                                                                                                                           |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/ops`                       | **Operator Cockpit**: kompakte Lage (`OperatorSituationStrip`), Fokus-Instrument (Symbol/TF/Family), Mirror-Freigabe (Approval Queue), Live Mirrors, Divergenz, Paper-vs-Live Outcome, Risk- und Drift-Hinweise, Links in tiefergehende Seiten. |
| `/terminal`                  | Live-Terminal (Charts, letztes Signal inkl. Lane, Stop-Budget, Instrument-Metadaten, Paper-Panel). Kurzlink **Ops-Lage** → `/ops`; Symbolwechsel ueber Watchlist/Fokus.                                                                         |
| `/signals`                   | Signal-Center: Tabellenansicht mit **Lane** (`meta_trade_lane`), Family-/Playbook-/Router-/Exit-Filter, Execution/Mirror/Telegram-Status, Detail mit Risk/Explain.                                                                              |
| `/live-broker`               | Broker-Zustand, Reconcile, Drift aus Laufzeitdetails, Kill-Switch-Übersicht (kein Ersatz für Exchange-UI).                                                                                                                                      |
| `/live-broker/forensic/[id]` | Trade-Forensik: Signal-/Marktkontext, Spezialistenroute, Release, Orders/Fills, Exit-Pläne, Telegram-/Gateway-Audit, Learning-/Review-Spur.                                                                                                     |
| `/health`                    | Gateway-Health: Execution-Gates, Ops-Summary (DB, Alerts, Outbox, Live-Broker-Kennzahlen), Services, Streams.                                                                                                                                   |
| `/learning`                  | Online-Drift-Gate, Registry v2 (Champion/Challenger), Drift-Events; Backtests eingeklappt.                                                                                                                                                      |

## Datenflüsse

- Server Components rufen `fetch*` aus `@/lib/api` auf (Gateway-HTTP). Fehler werden als Banner/Meldungen angezeigt, nicht als stilles Leeren.
- Live-Terminal ergänzt per SSE/Polling; Auth folgt denselben Gateway-Regeln wie andere Calls.
- Execution-/Telegram-Status im Dashboard stammen aus bestehenden Tabellen (`live.execution_decisions`, `live.execution_operator_releases`, `alert.alert_outbox`) oder authentifizierten Gateway-Read-Pfaden, nicht aus Browser-Secrets.

## Guards und sensible Aktionen

1. **Admin-Mutationen** (`NEXT_PUBLIC_ENABLE_ADMIN`, optional `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY`):
   - **Server-Proxy**: `POST /api/dashboard/admin/rules` und `POST /api/dashboard/admin/strategy-status` setzen `Authorization` nur aus **`DASHBOARD_GATEWAY_AUTHORIZATION`** (Server-ENV). Ohne Header: **503**, kein Weiterleiten ans Gateway.
   - **Direktmodus** (ohne Proxy): Browser sendet `X-Admin-Token` an das Gateway; nur für vertrauenswürdige Umgebungen gedacht.

2. **Client-Bestätigung**: Vor Regel-Speichern und Strategie-Lifecycle-Wechseln erscheint ein **`window.confirm`** mit Texten aus `@/lib/sensitive-action-prompts`. Das ersetzt **keine** serverseitige Autorisierung; es reduziert Fehlklicks.

3. **Auditierbarkeit**: Die UI protokolliert Aktionen nicht selbst. Nachweise entstehen über Gateway-/Service-Logs, DB-Audit-Tabellen oder Monitoring — je nach Deployment. `changed_by: "dashboard-ui"` im Strategy-Status-Body markiert die Quelle für Backend-Auswertung.

## Kill-Switch und Live-Gates

- Es gibt **keine** „Kill-Switch-Knopf“-Shortcuts in der UI ohne entsprechende, abgesicherte Backend-APIs. Operatoren sehen **Zähler und Status** (z. B. auf `/ops`, `/health`, Live-Broker) und steuern über dokumentierte Prozesse (Gateway, Runbooks).

## Tests (Smoke-Ebene)

- `pnpm --filter @bitget-btc-ai/dashboard test` — u. a. `operator-snapshot` (Lage-Zusammenfassung, Broker-Service-Wahl) und `sensitive-action-prompts`.
- `pnpm --filter @bitget-btc-ai/dashboard test` deckt zusaetzlich Operator-Queue-Heuristiken und deterministische Signal-Rationalen ab.
- `pnpm --filter @bitget-btc-ai/dashboard build` — Typecheck/Next-Build als Integrations-Smoke für die App.

Kein Playwright im Repo-Paket; Browser-E2E kann bei Bedarf ergänzt werden.
