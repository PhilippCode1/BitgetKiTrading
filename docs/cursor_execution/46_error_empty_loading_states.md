# 46 — Leer-, Lade- und Fehlerzustände (Console-Oberflächen)

**Bezug:** `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md`, `docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md`.

**Ziel:** Einheitliche, verständliche Nutzerzustände (Satz + Aktion + optionale Diagnostik) statt „nur leer“ oder Roh-Fehlerstrings. Gemeinsame Bausteine: `ConsoleFetchNotice`, `PanelDataIssue` (Fetch → `translateFetchError`), `EmptyStateHelp` (Client-Leerzustände), neu `ConsoleSurfaceNotice` (Server, i18n-Keys + optional API-Text), `ConsolePartialLoadNotice` (Teilladungen), `PageLoadingSkeleton` / route-`loading.tsx`.

---

## Gemeinsame Komponenten (Kurz)

| Baustein                   | Einsatz                                                                                        |
| -------------------------- | ---------------------------------------------------------------------------------------------- |
| `PanelDataIssue`           | Roh-Fehlerstring → `translateFetchError` → Titel/Body/Refresh + optional `<details>` technisch |
| `ConsoleFetchNotice`       | Darstellung aller Status-/Fehlerkarten (soft/alert), Schnellaktionen                           |
| `ConsoleSurfaceNotice`     | Wie oben, aber Titel/Refresh aus i18n-Keys (RSC)                                               |
| `ConsolePartialLoadNotice` | Mehrere Sektionen fehlgeschlagen, Rest nutzbar                                                 |
| `EmptyStateHelp`           | Client: Leerliste mit Schritten + optional Aktionen                                            |
| `PageLoadingSkeleton`      | Route-Loading (u. a. `/console`, `/console/terminal`)                                          |

---

## State-Matrix (Hauptseiten)

Legende: **Satz** = erklärender Kurztext · **Aktion** = primäre Nutzeraktion (z. B. Reload, Health, Anmeldung) · **Diag** = `?diagnostic=1` / technisches Detail.

### Health (`/console/health`)

| Zustand              | Umsetzung                               | Satz (Quelle)                                                                 | Aktion               | Diag       |
| -------------------- | --------------------------------------- | ----------------------------------------------------------------------------- | -------------------- | ---------- |
| loading              | Next `loading` / Teile suspend          | `ui.pageLoading.*`                                                            | —                    | —          |
| empty                | Tabellen „keine Alerts“ / leere Outbox  | `help.monitor.alertsEmpty`, `help.monitor.outboxEmpty`                        | Links im Header      | —          |
| partial              | — (ein gemeinsamer Catch)               | —                                                                             | —                    | —          |
| degraded             | Health-Panels, Warnungen, Integrationen | Panel-spezifische Texte                                                       | PDF/Links            | optional   |
| auth missing         | über `PanelDataIssue` bei 401           | `ui.fetchError.unauthorized.*`                                                | Schnellaktionen      | Rohmelding |
| upstream unavailable | 502/503 etc.                            | `ui.fetchError.bad_gateway.*` / `unreachable`                                 | Reload, Health       | Rohmelding |
| fatal error          | Catch beim parallelen Fetch             | `PanelDataIssue` + `HealthLoadFailureSurfaceCard` + `IssueCenterQuickActions` | Terminal/Quick-Links | Rohmelding |

### Terminal (`/console/terminal`)

| Zustand              | Umsetzung                                      | Satz                                    | Aktion              | Diag                   |
| -------------------- | ---------------------------------------------- | --------------------------------------- | ------------------- | ---------------------- |
| loading              | `terminal/loading.tsx` → `PageLoadingSkeleton` | `ui.pageLoading.*`                      | —                   | —                      |
| empty                | Keine Kerzen, kein Fetch-Fehler                | `EmptyStateHelp` (`help.liveEmpty.*`)   | Schritte + Aktionen | Surface-Diagnose-Karte |
| partial              | Transport-Hinweise (Polling, SSE aus)          | `live.terminal.transportHint*`          | Reload, Freeze      | SSE-Phase im `title`   |
| degraded             | Markt-Freshness-Banner                         | `live.terminal.freshness*`              | Reload              | Kerzen/Ticker-Zeilen   |
| auth missing         | `translateFetchError` im Client                | `ui.fetchError.unauthorized.*`          | Schnellaktionen     | `fetchErr`             |
| upstream unavailable | wie oben                                       | `bad_gateway` / `server_error`          | Reload              | `fetchErr`             |
| fatal error          | Initial-Fetch-Fehler                           | `ConsoleFetchNotice` + `fetchIssueLead` | Reconnect-Hinweis   | `fetchErr`             |

### Signals (`/console/signals`)

| Zustand              | Umsetzung                               | Satz                                   | Aktion          | Diag                 |
| -------------------- | --------------------------------------- | -------------------------------------- | --------------- | -------------------- |
| loading              | `/console/loading.tsx`                  | `ui.pageLoading.*`                     | —               | —                    |
| empty                | `SignalsTable` → `EmptyStateHelp`       | signals-leer-Keys                      | Aktionen        | —                    |
| partial              | Facets ok, Recent ok — Facet-Zähler „—“ | implizit                               | —               | —                    |
| degraded             | Facets-Umschlag leer/degradiert         | `ConsoleSurfaceNotice` + API-`message` | Schnellaktionen | `degradation_reason` |
| auth missing         | `PanelDataIssue` (Recent/Facets)        | `ui.fetchError.*`                      | Aktionen        | Roh                  |
| upstream unavailable | idem                                    | idem                                   | idem            | idem                 |
| fatal error          | beide Fetches fehlgeschlagen            | `PanelDataIssue`                       | idem            | idem                 |

### Signaldetail (`/console/signals/[id]`)

| Zustand                | Umsetzung                 | Satz                                                     | Aktion                        | Diag |
| ---------------------- | ------------------------- | -------------------------------------------------------- | ----------------------------- | ---- |
| loading                | `/console/loading.tsx`    | `ui.pageLoading.*`                                       | —                             | —    |
| empty (nicht gefunden) | kein `err`, kein `detail` | `ConsoleSurfaceNotice` + `pages.signalsDetail.notFound*` | Zurück-Link + Schnellaktionen | —    |
| partial                | —                         | —                                                        | —                             | —    |
| degraded               | —                         | —                                                        | —                             | —    |
| auth missing           | `PanelDataIssue`          | `unauthorized.*`                                         | Aktionen                      | Roh  |
| upstream unavailable   | `PanelDataIssue`          | `bad_gateway` / …                                        | Aktionen                      | Roh  |
| fatal error            | `PanelDataIssue`          | je nach Mapping                                          | Aktionen                      | Roh  |

### Strategies (`/console/strategies`)

| Zustand              | Umsetzung              | Satz                                                  | Aktion          | Diag |
| -------------------- | ---------------------- | ----------------------------------------------------- | --------------- | ---- |
| loading              | `/console/loading.tsx` | `ui.pageLoading.*`                                    | —               | —    |
| empty                | leere Tabelle          | `pages.strategiesList.tableEmpty`                     | —               | —    |
| partial              | —                      | —                                                     | —               | —    |
| degraded             | API `message`          | `ConsoleSurfaceNotice` + `ui.surfaceState.degraded.*` | Schnellaktionen | —    |
| auth missing         | `PanelDataIssue`       | `ui.fetchError.*`                                     | Aktionen        | Roh  |
| upstream unavailable | idem                   | idem                                                  | idem            | idem |
| fatal error          | idem                   | idem                                                  | idem            | idem |

### Strategiedetail (`/console/strategies/[id]`)

Wie Signaldetail: `PanelDataIssue` vs. `ConsoleSurfaceNotice` (Not Found) + `ui.surfaceState.notFound.refreshHint`.

### Paper (`/console/paper`)

| Zustand              | Umsetzung                                             | Satz                       | Aktion          | Diag                 |
| -------------------- | ----------------------------------------------------- | -------------------------- | --------------- | -------------------- |
| loading              | `/console/loading.tsx`                                | `ui.pageLoading.*`         | —               | —                    |
| empty                | Tabellen leer / `PaperReadNotice`                     | seiten-spezifisch          | —               | Gateway-Hinweise     |
| partial              | `Promise.allSettled`, einige Sektionen fehlgeschlagen | `ConsolePartialLoadNotice` | Schnellaktionen | Liste im `<details>` |
| degraded             | —                                                     | —                          | —               | —                    |
| auth missing         | `PanelDataIssue` (totalausfall)                       | `ui.fetchError.*`          | Aktionen        | Roh                  |
| upstream unavailable | idem / in Partial-Liste                               | idem                       | idem            | Zeilen               |
| fatal error          | alle Sektionen rejected                               | `PanelDataIssue`           | idem            | Roh                  |

### Live-Broker (`/console/live-broker`)

Wie Paper: `ConsolePartialLoadNotice` mit `pages.broker.partialLoad*`, `PanelDataIssue` bei Totalausfall, `EmptyStateHelp` / `sectionUnavailable` pro Karte.

### Shadow-Live (`/console/shadow-live`)

Wie Paper/Broker: `ConsolePartialLoadNotice` mit `pages.shadowLive.partialLoad*`.

### Account (`/console/account` und Unterseiten)

| Zustand              | Umsetzung                       | Satz              | Aktion                                | Diag                   |
| -------------------- | ------------------------------- | ----------------- | ------------------------------------- | ---------------------- |
| loading              | `account/loading.tsx`           | Skeleton          | —                                     | —                      |
| empty                | Snapshot-Felder „—“             | implizit          | Quick-Links                           | —                      |
| partial              | —                               | —                 | —                                     | —                      |
| degraded             | —                               | —                 | —                                     | —                      |
| auth missing         | Commerce 401 → `PanelDataIssue` | `unauthorized.*`  | (kein diagnostic-Default auf Account) | bei Bedarf erweiterbar |
| upstream unavailable | idem                            | `bad_gateway` / … | Reload                                | —                      |
| fatal error          | `PanelDataIssue`                | idem              | —                                     | —                      |

### Assist (`AssistLayerPanel` auf Health & Account)

| Zustand              | Umsetzung                                     | Satz                                                                  | Aktion                      | Diag             |
| -------------------- | --------------------------------------------- | --------------------------------------------------------------------- | --------------------------- | ---------------- |
| loading              | Button-Label / disabled                       | `pages.health.aiExplainLoadingShort`                                  | —                           | —                |
| empty                | keine Turns, kein Fehler                      | `ConsoleFetchNotice` + `ui.surfaceState.assist.empty*`                | Schnellaktionen             | —                |
| partial              | —                                             | —                                                                     | —                           | —                |
| degraded             | Fake-Provider-Banner                          | `pages.health.aiExplainFakeBanner`                                    | —                           | —                |
| auth missing         | HTTP-Fehler → `resolveOperatorExplainFailure` | im Body                                                               | ggf. neu anmelden           | —                |
| upstream unavailable | 502/503 etc.                                  | im Body                                                               | Reload                      | —                |
| fatal error          | Netzwerk / Parse / Abbruch                    | `ConsoleFetchNotice` alert + `ui.surfaceState.assist.callFailedTitle` | `ui.refreshHint` + Aktionen | sanitierter Text |

---

## Tests / Nachweise

- **UI-Komponenten:** `apps/dashboard/src/components/console/__tests__/ConsoleSurfaceNotice.test.tsx` (`ConsoleSurfaceNotice`, `ConsolePartialLoadNotice`).
- **Fehler-Mapping:** `apps/dashboard/src/lib/__tests__/user-facing-fetch-error.test.ts` — erweitert um `translateFetchError` für 401 und 503.
- **Typen:** `pnpm check-types` (Turbo) — grün nach Umsetzung.

### Manuelle Spot-Checks (kurz)

1. `/console/terminal` — harter Reload: Lade-Skeleton sichtbar.
2. `/console/paper` — eine API-Sektion simuliert fehlschlag: gelber Partial-Block mit Liste + Aktionen.
3. `/console/health?diagnostic=1` bei Fehler: Diagnose-Klappbox mit Rohstring.
4. Assist: ohne Absenden — Leer-Hinweis; nach fehlgeschlagenem Call — Alert-Karte mit Reload-Hinweis.

---

## Offene Punkte / [TECHNICAL_DEBT]

- **Ops / weitere Konsole-Routen:** gleiche Muster bei Bedarf auf `ops`, `integrations`, `learning` übernehmen (teilweise schon `PanelDataIssue`).
- **Account diagnostic:** Hauptseite setzt `diagnostic={false}` — bewusst; Operatoren-Diagnose primär unter Health.
- **Assist:** Roh-Fehler laufen durch `sanitizePublicErrorMessage`; kein zweites `translateFetchError`, da viele Meldungen bereits semantisch aufgelöst sind.
