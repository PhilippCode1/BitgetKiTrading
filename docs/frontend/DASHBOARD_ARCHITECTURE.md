# Dashboard Architecture & Frontend

Das Frontend (`/apps/dashboard`) bildet die zentrale Kommando- und Bedienoberfläche für das BitgetKiTrading-System. Es handelt sich um eine moderne Next.js (App Router) Applikation in TypeScript, die strikt zwischen Endkunden (Customer Portal) und System-Operatoren (Console) trennt.

## 1. Routing & Architektur (Next.js App Router)

Das System nutzt den Next.js App Router (`src/app/`) und erzwingt logische Trennung durch Route-Groups:

| Route-Group | Zweck |
|---|---|
| `(operator)` / `console` | Die Operator-Konsole für Administratoren und Händler. Hier liegen Routen wie `/console/live` (Live-Terminal) oder `/console/safety` (Safety-Latch Steuerung). |
| `(customer)` / `portal` | Das reduzierte Portal für Endkunden ohne tiefgreifende Steuerungsrechte. |
| `(public)` | Ungeschützte Routen (z.B. `/welcome`, `/onboarding`). |

**Architektur-Entscheidung:**
- **React Server Components (RSC)**: Werden für das Initiale Routing, Layouts (`layout.tsx`) und statische Data-Fetches genutzt. Das reduziert die Bundle-Size und beschleunigt das Rendering.
- **Client Components (`"use client"`)**: Alle interaktiven Panels (z.B. Charts, Live-Terminals, Safety-Panels) sind Client-seitig, da sie WebSocket-State, Polling oder React-Query benötigen.

## 2. Authentifizierung, Middleware & Autorisierung

Die `src/middleware.ts` ist der zentrale Wächter (Edge-Guard) des Frontends:

- **Locale & Onboarding**: Prüft `LOCALE_COOKIE_NAME` und `ONBOARDING_COOKIE_NAME`, um Nutzer bei Bedarf auf `/welcome` oder `/onboarding` umzuleiten.
- **Console Guard (`decideConsoleAccess`)**: Nutzt das JWT-Session-Handling (`operator-jwt.ts`, `portal-persona.ts`), um zu verhindern, dass "Customer"-Personas auf `/console/*` Pfade zugreifen. Endkunden werden rigoros in ihr Portal (`PORTAL_BASE`) umgeleitet.
- **Admin-Gates**: Kritische Admin-Seiten prüfen zusätzlich das Vorhandensein von Admin-Sessions (`hasAdminSessionFromDashboardEnv`).

## 3. Backend for Frontend (BFF) & Data Fetching

Das Next.js Backend (`src/app/api/`) fungiert als strikter Proxy (BFF) zu den internen Python-Microservices (z.B. via `api-gateway`).

```mermaid
graph LR
    A[Client Component] -->|Fetch / React Query| B[Next.js API Route (BFF)]
    B -->|gateway-upstream-fetch.ts| C[API Gateway]
    C --> D[Microservices (Python/Rust)]
```

- **Upstream Fetching**: `src/lib/gateway-upstream-fetch.ts` kapselt sämtliche Calls zum API Gateway. Es inkludiert automatische Authorization-Header, Trace-IDs und implementiert Retry-Logiken (`fetchGatewayGetWithRetry`) für idempotente GET-Requests bei transienten Netzwerkfehlern.
- **State Management**: Der `DashboardQueryProvider` bindet `@tanstack/react-query` an. Dies ermöglicht asynchrones Caching, Revalidation und Optimistic Updates.
- **Live Data (SSE)**: Für Livedaten (z.B. im `LiveTerminalClient.tsx`) wird `startManagedLiveEventSource` genutzt, welches Server-Sent-Events (SSE) konsumiert und automatische Reconnects bei Stale-Verbindungen (über Ping-Watchdogs) durchführt.

## 4. Operator Console (Kommandozentrale)

Die Komponenten im Verzeichnis `src/components/` stellen das operative Dashboard für das System dar. Sie sind extrem datendicht und funktional.

- **`LiveTerminalClient.tsx`**: Die Hauptansicht für Live-Märkte. Kombiniert `ChartPanel`, `SignalPanel`, `MicrostructurePanel` und `LiveDataLineagePanel`. Es verwaltet asynchrone SSE-Verbindungen und warnt vor "Stale" Data.
- **`SelfHealingHubClient.tsx`**: Das UI für den Self-Healing Mechanismus. Zeigt Incidents an (`SelfHealingIncident`) und erlaubt Manuelle Overrides ("Full Recheck", "Restart Worker") sowie die Anzeige der `SituationAiExplainPanel` für semantische Triage-Logs.
- **`ExecutionSafetyPanel.tsx`**: Ein dediziertes Panel in `/safety`, mit dem Operatoren harte Sicherheitsaktionen triggern können: `kill_switch_arm`, `safety_latch_release`, `cancel_all` und `emergency_flatten`. Aktionen werden doppelt verifiziert.
- **Signal Explanation (`/signals`)**: Komponenten wie `SignalDetailTechnicalCollapsible.tsx` und `SignalDetailStoredExplainSection.tsx` visualisieren die Feature-Matrix und den deterministischen Veto-Ablauf eines Signals.

## 5. Internationalisierung (i18n) & UI-Design

- **i18n**: Übersetzungen werden statisch über JSON-Dateien (`src/messages/de.json`, `src/messages/en.json`) geladen. Die Client-Komponenten konsumieren diese über den Custom-Hook `useI18n()` (aus `I18nProvider`).
- **Theming & CSS**: Das Design verzichtet weitgehend auf große UI-Bibliotheken und stützt sich stattdessen auf Vanilla CSS (`globals.css`, `theme.css`) in Kombination mit CSS-Variablen. Dies ermöglicht ein schnelles, responsives "Glassmorphism" Design mit minimaler Bloat-Gefahr, exakt ausgerichtet auf die Bedürfnisse eines hochdichten Trading-Terminals.
