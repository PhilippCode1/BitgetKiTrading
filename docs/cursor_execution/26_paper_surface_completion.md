# 26 — Paper-Oberfläche: Cockpit-Vertrag, Datenpfad, Zustände

## Ziel

Die Route **`/console/paper`** ist **vollständig nutzbar**: parallele Lesepfade, **typstabile** Defaults, verständliche **Leer-, Teil- und Fehlerzustände**, keine halbfertigen Flächen. Tabellen folgen **i18n** (`tables.paperOpen` / `tables.paperTrades`). Ledger nutzt **primär** `GET /v1/paper/ledger/recent` mit **Fallback** auf `account_ledger_recent` aus den Metriken, wenn der Ledger-Fetch fehlschlägt.

Siehe auch: [17 — Paper-Broker-Konsistenz](17_paper_broker_consistency.md).

## Gateway (Upstream)

Alle Routen liefern `GatewayReadEnvelope` (`status`, `message`, `empty_state`, `degradation_reason`, `next_step`) plus Payload.

| Methode | Pfad                        | Nutzung Dashboard                                                                              |
| ------- | --------------------------- | ---------------------------------------------------------------------------------------------- |
| GET     | `/v1/paper/positions/open`  | Offene Positionen                                                                              |
| GET     | `/v1/paper/trades/recent`   | Performance-Kennzahlen + Tabelle „Letzte Trades“                                               |
| GET     | `/v1/paper/metrics/summary` | Konto, Gebühren, Funding, Equity-Kurve, **Kurz-Ledger** (derzeit bis **12** Zeilen im Gateway) |
| GET     | `/v1/paper/ledger/recent`   | **Hauptquelle** Ledger-Tabelle (Limit 1–100, UI: 40)                                           |
| GET     | `/v1/paper/journal/recent`  | Journal-Tabelle                                                                                |
| GET     | `/v1/system/health`         | Ausführungspfad-Kurzinfo                                                                       |

Implementierung Gateway: `services/api-gateway/src/api_gateway/routes_paper_proxy.py`.

## BFF (Dashboard)

Browser: `GET /api/dashboard/gateway/v1/...` (same-origin).  
Server Components: direkter Gateway-GET mit Auth (siehe `apps/dashboard/src/lib/api.ts`, `getJson`).

Client-Funktionen (Auszug): `fetchPaperOpen`, `fetchPaperTradesRecent`, `fetchPaperMetricsSummary`, `fetchPaperLedgerRecent`, `fetchPaperJournalRecent`, `fetchSystemHealthCached`.

## UI-Abschnitte (`console/paper`)

1. **Kopf** — Titel, Untertitel mit Chart-Symbol.
2. **Fehlerbanner** — nur wenn **alle** parallelen Fetches fehlschlagen (`PanelDataIssue`).
3. **Teillast-Hinweis** — Liste der fehlgeschlagenen Sektionen (`pages.paper.partialLoad*`).
4. **Ausführungsmodus** — `ExecutionPathSummaryList`, wenn Health geladen.
5. **Admin-Hinweis** — statischer Text zu Demo-Konto-APIs.
6. **Offene Demo-Positionen** — `PaperReadNotice` + `OpenPositionsTable`.
7. **Demo-Konto & Kosten** — `PaperReadNotice` + Kontowerte + Gebühren/Funding.
8. **Performance** — `PaperReadNotice` + Kennzahlen aus `derivePaperClosedTradeStats(trades)` (nur geschlossene Zeilen mit `closed_ts_ms` und `pnl_net_usdt`).
9. **Equity-Kurve** — `ProductLineChart`, Leertext abhängig von Konto/Kurve.
10. **Konten-Ledger** — bei erfolgreichem Ledger-Fetch: `PaperReadNotice` + Tabelle; bei Fetch-Fehler: Hinweis `pages.paper.ledgerFallbackFromMetrics` + Zeilen aus `metrics.account_ledger_recent`.
11. **Journal** — `PaperReadNotice` + Tabelle, Detail-Vorschau `previewPaperJournalDetail`.
12. **Letzte Trades** — `PaperReadNotice` + `TradesTable`.

## Envelope-UI (`PaperReadNotice`)

- **`degraded`**: Nutzer-`message` oder `pages.paper.dataDegradedGeneric`; optional **`next_step`** mit `pages.paper.degradedNextStep`.
- **`empty_state` + `message`**: Server-`message` plus optional `next_step` (gleiches Muster).

## Hilfsmodule

- `apps/dashboard/src/lib/paper-console.ts` — `paperSectionFetchErrorMessage`, `previewPaperJournalDetail`, `derivePaperClosedTradeStats`.
- `apps/dashboard/src/lib/paper-response-defaults.ts` — u. a. `emptyPaperLedgerResponse`.

## Nachweise (lokal)

1. **Typen:** im Repo-Root `pnpm check-types`.
2. **Dashboard-Tests (Paper):**  
   `pnpm --filter @bitget-btc-ai/dashboard test -- --testPathPattern="paper-(console|response-defaults)|PaperTables|paper-read-notice" --runInBand`
3. **Gateway-Smoke (laufender Stack, Port 8000):**  
   `bash tests/dashboard/test_routes_smoke.sh` — enthält `curl` für alle Paper-Leserouten oben.

## Bekannte Grenzen

- **`account_ledger_recent`** in den Metriken ist absichtlich **kürzer** als die vollständige Ledger-Route; bei Fallback weist die UI darauf hin.
- **Doppelte `PaperReadNotice`** bei „Letzte Trades“ (Performance-Karte und untere Tabelle) ist bewusst: gleicher Envelope, konsistente Hinweise bei leer/degradiert.
