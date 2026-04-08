# API- und Schnittstellen-Status (Prompt 6)

**Stand:** 2026-04-02 — **technische Code-Diagnose** (kein Laufzeit-Test aller Endpunkte gegen einen live-Gateway in diesem Schritt).  
**Codebasis:** `apps/dashboard` (Next.js BFF unter `/api/**`, Client/SSR über `src/lib/api.ts`).

---

## Umgebungsvariablen (relevant)

| Variable                                   | Wo                              | Zweck                                                                                                                                                                                     |
| ------------------------------------------ | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `API_GATEWAY_URL`                          | Server (`server-env.ts`)        | Basis-URL des API-Gateways für SSR/BFF. **Pflicht** bei `next start` (Production); in `development`/`test` optional Fallback auf `NEXT_PUBLIC_API_BASE_URL` bzw. `http://127.0.0.1:8000`. |
| `NEXT_PUBLIC_API_BASE_URL`                 | Build-Zeit / Browser (`env.ts`) | Öffentliche Gateway-URL für **direkte** Browser-`fetch`/`EventSource`. Production-Build: kein stiller Localhost-Fallback — Variable explizit setzen.                                      |
| `DASHBOARD_GATEWAY_AUTHORIZATION`          | Server only                     | Vollständiger `Authorization`-Header (z. B. `Bearer …`) für Gateway; **Pflicht** für alle `requireOperatorGatewayAuth()`-Routen.                                                          |
| `PAYMENT_MOCK_WEBHOOK_SECRET`              | Server                          | Mock-Einzahlung abschließen (Dashboard → Gateway-Webhook).                                                                                                                                |
| `COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE` | Server                          | Spiegel Telegram-Zwang (zusätzlich zu `NEXT_PUBLIC_…`).                                                                                                                                   |
| `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY`       | Public                          | `true`: Browser ruft `/api/dashboard/*` auf; Server hängt `Authorization` an.                                                                                                             |
| `NEXT_PUBLIC_ENABLE_ADMIN`                 | Public                          | Admin-UI ein/aus.                                                                                                                                                                         |

---

## Zentrale Client-Bibliothek `lib/api.ts`

| Verbindung                          | Vorher (Fehlerbild)                                                      | Ursache                                      | Reparatur (umgesetzt)                                                                                                                                                                                                                       | Teststatus                                  |
| ----------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `getJson()` → alle SSR-Gateway-GETs | Nur `path` + HTTP-Status; keine Timeouts; JSON-Parse-Fehler ohne Kontext | Minimales Error-Handling; Body nicht gelesen | **Einmal** `res.text()`, bei Fehler `detail` aus JSON (`detail`/`message`) oder Klartext; **60s** Timeout SSR / **45s** Browser; `console.error` auf dem Server mit `path`, `status`, `detail`-Ausschnitt; klare deutsche Nutzer-/Dev-Texte | statisch (tsc); Laufzeit: manuell mit Stack |
| `getJsonViaDashboardBff()`          | Doppeltes `res.json()`-Risiko; kein Timeout                              | Alte Implementierung                         | Text-Body, gleiche Detail-Extraktion, **45s** Timeout, `console.error` im Browser bei Fehlern                                                                                                                                               | statisch                                    |
| `fetchLiveState` (Browser + Proxy)  | Fehlerbody teils verschluckt bei nicht-JSON                              | `res.json()` auf Fehlerantwort               | Wie BFF: `text()` + Parse + Timeout + Logging                                                                                                                                                                                               | statisch                                    |

---

## Next.js BFF (`app/api/dashboard/**/route.ts`)

Alle unten genannten Routen nutzen typischerweise `requireOperatorGatewayAuth()` → bei fehlendem `DASHBOARD_GATEWAY_AUTHORIZATION` **503** mit JSON `{ detail: "…" }`.

| Verbindung                                                                                                    | Aktueller Fehler (wenn ENV falsch) | Ursache                        | Reparatur / Verhalten                                                        | Teststatus  |
| ------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ------------------------------ | ---------------------------------------------------------------------------- | ----------- |
| `GET /api/dashboard/live/state`                                                                               | 503 oder 502                       | Kein Auth / Gateway down       | Bereits: Timeout 25s upstream, `upstreamFetchFailedResponse` bei Netzwerk    | Code-Review |
| `GET /api/dashboard/live/stream`                                                                              | 503 oder SSE bricht ab             | Kein Auth / upstream `!res.ok` | **Neu:** `console.error` mit Status + Body-Snippet bei upstream-Fehler       | Code-Review |
| `GET /api/dashboard/system/health`                                                                            | 503 / 502                          | wie oben                       | Timeout 60s                                                                  | Code-Review |
| `GET /api/dashboard/monitor/alerts/open`                                                                      | wie oben                           | wie oben                       | Timeout wie Route                                                            | Code-Review |
| `GET /api/dashboard/alerts/outbox/recent`                                                                     | wie oben                           | wie oben                       | wie oben                                                                     | Code-Review |
| `GET/POST/PATCH …/admin/rules`                                                                                | wie oben                           | wie oben                       | POST/PUT je nach Implementierung                                             | Code-Review |
| `POST …/admin/strategy-status`                                                                                | wie oben                           | wie oben                       | JSON-Body durchgereicht                                                      | Code-Review |
| `GET /api/dashboard/health/operator-report`                                                                   | wie oben                           | PDF/Binary-Pfad                | eigene Route                                                                 | Code-Review |
| Commerce: `customer/me`, `balance`, `integrations`, `payments`, `history`, `usage-*`, Deposit-Flows, Telegram | 503/502/4xx vom Gateway            | Modul aus / Auth / Business    | Durchreichen von Status + Body; Timeouts 12s typisch                         | Code-Review |
| `GET /api/dashboard/edge-status`                                                                              | —                                  | Diagnose-Route                 | Kein Gateway-Auth für `/health`; optional Auth-Probe auf `/v1/system/health` | Code-Review |

---

## Weitere Fetch-Stellen (Dashboard)

| Verbindung                                                            | Fehlerbild                                    | Ursache                   | Hinweis                                                            |
| --------------------------------------------------------------------- | --------------------------------------------- | ------------------------- | ------------------------------------------------------------------ |
| `AdminRulesPanel` / `StrategyStatusActions`                           | HTTP-Fehler nur als kurzer Text               | BFF oder direktes Gateway | Nutzer sieht `strategyStatus.errHttp` o. Ä.; kein zentraler Parser |
| `TelegramAccountPanel`, `DepositCheckoutPanel`, `CustomerProfileForm` | `/api/dashboard/commerce/…`                   | Wie BFF-Tabelle           | Fehler aus `res.text()` teils roh                                  |
| `ConsoleTelegramGate`                                                 | Integrationen 404/503                         | Commerce nicht aktiv      | Gate setzt `ready` bei `!res.ok` — bewusst nicht hart blockierend  |
| `OnboardingWizard`                                                    | `/api/onboarding/status`                      | Cookie/JSON               | eigene Route                                                       |
| `UiModeSwitcher`, `I18nProvider`, `WelcomeLanguageClient`             | `/api/dashboard/preferences/*`, `/api/locale` | Kein Gateway              | Lokale Cookies/Preferences                                         |
| `operator-session.canAccessAdminViaServer`                            | still `false`                                 | Netzwerk/401              | **Neu:** `console.warn` mit `base` und Fehlermeldung (ohne Secret) |

---

## Gateway-Pfade (SSR über `getJson`, Basis `API_GATEWAY_URL`)

Alle mit Header `Authorization: DASHBOARD_GATEWAY_AUTHORIZATION` **nur auf dem Server**.

- `/v1/live/state` (Browser nur ohne Proxy — siehe unten)
- `/v1/signals/*`, `/v1/paper/*`, `/v1/news/*`, `/v1/registry/strategies*`
- `/v1/learning/*`, `/v1/backtests/runs`
- `/v1/system/health` (Browser mit Proxy → BFF)
- `/v1/market-universe/status`
- `/v1/monitor/alerts/open`, `/v1/alerts/outbox/recent` (Browser mit Proxy → BFF)
- `/v1/admin/rules`
- `/v1/live-broker/*` inkl. Forensic-Timeline
- `/v1/commerce/*`

**Browser + `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=false`:** viele dieser Aufrufe gehen gegen `NEXT_PUBLIC_API_BASE_URL` **ohne** Authorization → erwartbar **401/403**, sofern das Gateway keine öffentliche anonyme Lesespanne hat. Das ist **kein Code-Bug**, sondern Konfigurationsmodus.

---

## SSE / `EventSource` (`lib/sse.ts`)

| Verbindung                                       | Risiko                  | Ursache                         | Hinweis                                                                      |
| ------------------------------------------------ | ----------------------- | ------------------------------- | ---------------------------------------------------------------------------- |
| `EventSource` → `/v1/live/stream` (Cross-Origin) | Verbindung schlägt fehl | **CORS** + ggf. Auth am Gateway | Nur im **Direct-Modus**; mit Proxy: same-origin `/api/dashboard/live/stream` |
| `onerror` schließt `EventSource`                 | Kein Auto-Reconnect     | bewusst `es.close()`            | Terminal zeigt dann Polling-Hinweis                                          |

---

## Auth / Middleware

- **`middleware.ts`:** `/api/*` ist von Locale-Redirect **ausgenommen** — APIs bleiben erreichbar.
- **CORS:** Next-BFF ist same-origin; CORS betrifft nur direkte Browser→Gateway-Aufrufe.

---

## Änderungen in Prompt 6 (kurz)

1. `getJson` / `getJsonViaDashboardBff`: vollständige Body-Auswertung, Timeouts, Server-/Client-Logs, verständliche Fehlermeldungen.
2. `fetchLiveState` (BFF-Zweig): gleiche Robustheit.
3. `live/stream` BFF: Logging bei upstream `!res.ok`.
4. `canAccessAdminViaServer`: `console.warn` statt stillem `catch`.

Siehe auch: [`project-audit.md`](../project-audit.md), [`docs/dashboard-console-functionality.md`](dashboard-console-functionality.md).
