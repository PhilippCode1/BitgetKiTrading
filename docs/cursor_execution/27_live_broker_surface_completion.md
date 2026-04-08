# 27 — Live-Broker-Oberfläche: Vertrag, Zustände, Nachweise

**Stand:** 2026-04-05

**Bezug:** [18 — Live-Broker, Safety und Operator-Sicht](18_live_broker_and_safety.md), [04 — TypeScript grün](04_typescript_green.md), [08 — ENV/Auth](08_env_profiles_and_secrets_sync.md), Handoff zu Gateway/BFF.

## Ziel

Die Operator-Route **`/console/live-broker`** und **`/console/live-broker/forensic/[id]`** sind **betrieblich brauchbar**: parallele Lesepfade ohne „ein Fehler killt die ganze Seite“, **sichtbare** Unterscheidung zwischen _deaktiviert_, _blockiert_, _leer_, _degradiert_ und _Fetch fehlgeschlagen_, einheitliche **Gateway-Envelope-Hinweise** (`GatewayReadNotice`) und **i18n** unter `pages.broker.*` / `pages.forensic.*` / `console.gatewayEnvelope.*`.

## Gateway-Leserouten (`/v1/live-broker/*`)

| Route                                    | Dashboard-Funktion                | Nutzung UI                                                                                              |
| ---------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `GET /runtime`                           | `fetchLiveBrokerRuntime`          | Strip `operator_live_submission`, Execution-Pfad, Bitget-Diagnose, Order-Counts, Instrumente, Reconcile |
| `GET /kill-switch/active`                | `fetchLiveBrokerKillSwitchActive` | Tabelle aktiv; leerer Zustand mit Gateway-Text oder `killSwitchInactiveExplain`                         |
| `GET /kill-switch/events/recent`         | `fetchLiveBrokerKillSwitchEvents` | Tabelle (max. 20 Zeilen)                                                                                |
| `GET /audit/recent`                      | `fetchLiveBrokerAuditRecent`      | Safety-Audit-Tabelle                                                                                    |
| `GET /decisions/recent`                  | `fetchLiveBrokerDecisions`        | Decisions inkl. Forensic-Link                                                                           |
| `GET /orders/recent`                     | `fetchLiveBrokerOrders`           | Orders                                                                                                  |
| `GET /fills/recent`                      | `fetchLiveBrokerFills`            | Fills                                                                                                   |
| `GET /orders/actions/recent`             | `fetchLiveBrokerOrderActions`     | HTTP/Exchange-Spur                                                                                      |
| `GET /executions/{id}/forensic-timeline` | `fetchLiveBrokerForensicTimeline` | Forensic-Detailseite                                                                                    |

Mutationen (Safety) bleiben über `routes_live_broker_safety.py` / Operator-Doku — diese Datei beschreibt die **Lesesicht**.

Implementierung: `services/api-gateway/src/api_gateway/routes_live_broker_proxy.py`.

## BFF / Dashboard-Abruf

- **Browser:** `GET /api/dashboard/gateway/v1/live-broker/...`
- **Server Components:** `apps/dashboard/src/lib/api.ts` → `getJson` mit Gateway-Auth (siehe `DASHBOARD_GATEWAY_AUTHORIZATION`, [08](08_env_profiles_and_secrets_sync.md)).

## Runtime- und Safety-Zustände (final)

Quelle: `operator_live_submission` in **`GET /v1/live-broker/runtime`** (siehe [18](18_live_broker_and_safety.md)).

| `lane`                         | Bedeutung (Kurz)                   | UI             |
| ------------------------------ | ---------------------------------- | -------------- |
| `live_lane_ready`              | Live-Pfad laut Snapshot bereit     | grüner Strip   |
| `live_lane_disabled_config`    | Live absichtlich aus (Modus/Flags) | Warn-Strip     |
| `live_lane_blocked_safety`     | Kill-Switch und/oder Latch         | Critical-Strip |
| `live_lane_blocked_exchange`   | Bitget nicht handelsfähig          | Warn-Strip     |
| `live_lane_blocked_upstream`   | Upstream ungesund                  | Critical-Strip |
| `live_lane_degraded_reconcile` | Reconcile ≠ ok                     | Critical-Strip |
| `live_lane_unknown`            | Reconcile unklar                   | Warn-Strip     |

`reasons_de`: erklärende Sätze; `safety_kill_switch_count`, `safety_latch_active`: kompakte Metazeile im Strip (`LiveSubmissionOperatorStrip`).

**Zusätzlich:** Envelope der Runtime (`status`, `message`, `empty_state`, `next_step`) wird im Runtime-Panel über **`GatewayReadNotice`** gezeigt — z. B. „Kein Live-Broker-Runtime-Datensatz“ vs. DB-degradiert.

## Gemeinsame Komponenten / Hilfen

- `apps/dashboard/src/components/console/GatewayReadNotice.tsx` — Envelope-Hinweise (ersetzt duplizierte Paper-Logik; `PaperReadNotice` re-exportiert dieselbe Komponente).
- `apps/dashboard/src/lib/gateway-fetch-errors.ts` — `gatewayFetchErrorMessage` für `Promise.allSettled`.
- `apps/dashboard/src/lib/live-broker-console.ts` — `prettyJsonLine`, `recordHasKeys`, `orderStatusCountsNonEmpty`.

## UI-Verhalten `/console/live-broker`

- **Acht parallele Fetches** (`Promise.allSettled`): Teillast-Banner mit Sektionsliste bei Teilfehlern; **vollständiger** Ausfall nur wenn alle acht fehlschlagen (`PanelDataIssue`).
- **Tabellen:** bei leerer Liste und ohne serverseitige `message` im Envelope → `pages.broker.tableEmptyOperational`; bei `empty_state` + `message` → nur `GatewayReadNotice` (kein doppelter Kill-Switch-Hinweis).
- **Bitget-Panel:** erklärender Text, wenn keine Privatdiagnose im Reconcile (`bitgetNoDiagnostic`).
- **Order-Status-Zähler / Instrument / Reconcile:** eigene Leer-Hinweise statt leerer Überschriften.

## Forensic-Seite

- Bei **`status === "degraded"`** auf der Timeline-Response: `GatewayReadNotice` oben.
- Timeline-Tabelle und Kopfzeilen über `pages.forensic.*`; JSON über `prettyJsonLine`.

## Nachweise (Befehle)

```powershell
cd c:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai
pnpm check-types
cd apps\dashboard
pnpm exec jest --testPathPattern="paper-read-notice|live-broker-console|gateway-fetch-errors|PaperTables" --runInBand
```

**API-Smoke** (laufendes Gateway, z. B. Port 8000):

```bash
bash tests/dashboard/test_routes_smoke.sh
```

Enthält u. a. `curl` für `/v1/live-broker/runtime`, `decisions/recent`, `kill-switch/active`, `audit/recent`.

## Manuelle Prüfpfade (kurz)

1. **`/console/live-broker`** mit laufendem Stack: Runtime-Panel gefüllt, Strip zeigt erwartete `lane`; Kill-Switch leer → verständlicher Text.
2. **Gateway stoppen oder Auth entfernen:** Teillast-Banner oder Gesamtfehler, aber keine leeren Tabellen ohne Text.
3. **Forensic:** gültige `execution_id` aus Decisions öffnen; bei unbekannter ID → `notFoundTitle` / `notFound`.

## Beispiel Runtime (Safety / Konfiguration)

```json
{
  "status": "ok",
  "item": {
    "operator_live_submission": {
      "lane": "live_lane_disabled_config",
      "reasons_de": [
        "Shadow-Modus: Börsen-Submission (live_submission_enabled) ist aus — typisch bis Live explizit freigeschaltet wird."
      ],
      "safety_kill_switch_count": 0,
      "safety_latch_active": false
    }
  }
}
```

## Offene Punkte

- `[FUTURE]` Ops-Seite (`/console/ops`) und Live-Broker-Seite teilen weiterhin ähnliche Daten — bei Bedarf View-Model weiter bündeln; Live-Broker-Seite ist die **fokussierte** Journal-Sicht.
- `[TECHNICAL_DEBT]` Einige Forensic-JSON-Panels haben noch feste englische Titel („Orders“, „Risk Snapshot“) — optional nachziehen, wenn Übersetzungsbedarf besteht.
