# Projekt-Audit — bitget-btc-ai

**Stand:** 2026-04-02 (Code-basiert; kein Laufzeit-Stack in diesem Audit gestartet)  
**Methodik:** Struktur, Routing, `apps/dashboard`-Codepfade, `services/*`, `docker-compose.yml`, Stichproben in API-/Env-Schichten, `pnpm exec tsc --noEmit` und `pnpm test` im Dashboard-Paket.

---

## Kurzüberblick Architektur

| Bereich           | Befund                                                                                                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**      | Next.js 16 App Router unter `apps/dashboard` (`@bitget-btc-ai/dashboard`), Turbo-Monorepo mit `shared/ts`.                                                                                                                                           |
| **Routing**       | Öffentlich: `/` (`(public)`), `/welcome`, `/onboarding`. Operator: `/console/*` (`(operator)/console`). API-Routen: `apps/dashboard/src/app/api/**`.                                                                                                 |
| **Middleware**    | `apps/dashboard/src/middleware.ts`: ohne Locale-Cookie → Redirect `/welcome`; mit Locale aber ohne abgeschlossenes Onboarding → `/onboarding?returnTo=…`. Keine klassische Benutzer-Login-Session im Middleware-Layer.                               |
| **Datenfluss UI** | Server Components rufen `fetch` gegen `API_GATEWAY_URL` mit optionalem `DASHBOARD_GATEWAY_AUTHORIZATION` (`apps/dashboard/src/lib/api.ts`). Browser: `NEXT_PUBLIC_API_BASE_URL` oder BFF unter `/api/dashboard/*` (z. B. Live-State bei Proxy-Flag). |
| **Backend**       | Python-Microservices (u. a. `api-gateway`, `signal-engine`, `paper-broker`, `live-broker`, `learning-engine`, `llm-orchestrator`, `news-engine`, …) laut `docker-compose.yml`.                                                                       |
| **KI**            | `services/llm-orchestrator` (OpenAI strukturiert, Fake-Provider, Redis, Schemas unter `shared/contracts/schemas`). News-Anreicherung u. a. `services/news-engine`.                                                                                   |
| **Env**           | Zentral dokumentiert in `.env.example`; Profile in `.env.local.example`, `.env.shadow.example`, `.env.production.example`.                                                                                                                           |

**Build-/Testsignal (lokal ausgeführt):** `apps/dashboard`: TypeScript ohne Emit erfolgreich; Jest — 11 Suites / 50 Tests grün.

---

## 1. Was fertig und tragfähig wirkt

- **Compose-Stack** mit Postgres, Redis, Marktdaten-/Feature-/Signal-Pipeline, Gateway, Paper/Live-Broker, Learning, LLM-Orchestrator, Monitor/Alert, optionalem Dashboard-Image (`docker-compose.yml`).
- **Dashboard-Konsole** mit breiter Abdeckung: Ops, Terminal, Approvals, Marktuniversum, Signale/Strategien, News, Health, Live-Broker inkl. Forensic-Pfad, Paper, Shadow-vs-Live, Learning (viele Gateway-Endpunkte parallel), Account-Subtree (Balance, Broker, Deposit, Payments, Usage, History, Telegram, Sprache, Profil), Admin, Usage.
- **BFF-Schicht** für gateway-authentifizierte Server-Routen (`gateway-bff.ts`, diverse `route.ts` unter `api/dashboard/…`) inkl. verständlicher 502-Texte bei nicht erreichbarem Gateway (`gateway-upstream.ts`).
- **Commerce/Telegram-Integration** über BFF-Routen; **Telegram-Gate** in der Console (`ConsoleTelegramGate.tsx`) mit Ladezustand.
- **i18n-Grundlage** (`messages/de.json`, `en.json`, Locale-API/Cookies) für große Teile der Shell und öffentlichen Bereich.
- **Shared Contracts** (OpenAPI, JSON-Schemas) und **shared-ts** für Event-Streams.
- **Operative Skripte** (`scripts/*.ps1`) für lokale Stack-Lifecycle laut Root-`package.json`.

---

## 2. Was unvollständig ist

- **I18n-Lücken (Rest):** `capabilities/page.tsx` und `learning/page.tsx` sind überwiegend über Setzungen in `messages/*` abgedeckt. **Größere Lücke:** `signals/[id]/page.tsx` — viele `<details>`-Zusammenfassungen und technische Labels noch **fest deutsch** (Erweiterung möglich über `pages.signalsDetail.*`).
- **Admin-/Sicherheitsmodell:** Bei `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=false` zeigt `resolveShowAdminNav()` die Admin-Navigation, obwohl Schreibzugriff dann vom Browser mit `X-Admin-Token` abhängt (`AdminRulesPanel.tsx`, `operator-session.ts`) — erhöht Risiko für Fehlkonfiguration und „tote“ Admin-UI ohne funktionierendes Speichern.
- **Produkt vs. Demo:** `LLM_USE_FAKE_PROVIDER`, Mock-Zahlungen (`mock-complete` Route, `DepositCheckoutPanel`) und Fixture-Flags sind für lokale Demos gedacht; Übergang zu harten Produktanforderungen ist dokumentations- und env-abhängig, nicht „fertig gekapselt“ in der UI.
- **Workspace:** Zusätzliche Ordner wie `Neuer Ordner/` mit `.env`-Duplikaten — erhöht Verwechslungsgefahr (kein funktionaler Bug, aber Wartungsrisiko).

---

## 3. Was „kaputt“ sein kann (kontextabhängig / keine Compiler-Fehler nachweisbar)

> Keine durch Typecheck/Jest nachgewiesenen Defekte im Dashboard. „Kaputt“ = typische Laufzeit- oder Betriebszustände.

- **Ohne laufendes API-Gateway oder falsche URL:** Server- und Client-Fetches scheitern; Seiten zeigen `API: …`-Fehler — erwartetes Verhalten, aber Produkt wirkt defekt.
- **Ohne `DASHBOARD_GATEWAY_AUTHORIZATION`:** BFF-Routen antworten mit **503** und erklärendem JSON (`requireOperatorGatewayAuth`) — korrekt implementiert, aber ohne Setup unbenutzbar.
- **LLM-Orchestrator:** Ohne `OPENAI_API_KEY` und ohne Fake-Provider keine Provider-Kette (`service.py`); Gateway-Matrix markiert LLM ggf. als `degraded` — kein reiner Frontend-Bug.
- **Zahlungen:** Mock-Pfad braucht abgestimmtes `PAYMENT_MOCK_WEBHOOK_SECRET` zwischen Dashboard und Gateway; sonst schlägt der Abschluss fehl.

---

## 4. Was für ein funktionierendes Produkt (noch) fehlen kann

- **Endkunden-Authentifizierung** abgestimmt auf Middleware (aktuell Locale + Onboarding-Cookies, kein Account-Login im gleichen Sinne wie ein SaaS-Portal).
- **Durchgängige Produktionskonfiguration:** Einheitliches Profil (Shadow → Live-Gates), Secrets/Vault, CORS/URLs, `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true` wo sinnvoll, Stripe/Production-Payment-Flows abgeschlossen getestet.
- **E2E-/Vertrags-Tests** über Gateway + Dashboard (bestehende Tests sind überwiegend Unit-Ebene im Dashboard).
- **Konsistente UX-Standards** über alle Console-Seiten: Ladezustände, leere Listen, Fehlertexte, Mobile — explizit gegen Checkliste (siehe Arbeitsregeln) abarbeiten.
- **Betrieb:** Backups, Alert-Runbooks, SLAs — teils in `docs/` angedeutet; „fertiges Produkt“ braucht operativ geschlossene Kreise.

---

## Feste Arbeitsregeln (für alle weiteren Schritte)

Ausführlicher, verbindlicher **Sprach- und Inhaltsleitfaden:** [`content-style-guide.md`](content-style-guide.md) (Ton, Anrede, Fehler, Leerzustände, KI-Texte, Umsetzung in `messages/*.json`).

---

1. **Benutzerfreundlichkeit:** Jede neue oder geänderte Oberfläche braucht klare Primäraktion, erkennbare Ladezustände, nachvollziehbare Fehlermeldungen (kein roher Stacktrace für Endnutzer), sinnvolle Leerzustände („Keine Daten“ + nächster Schritt).
2. **Sprache:** Deutsch als Primärsprache für sichtbare Texte: grammatikalisch korrekt, natürlich freundlich, ohne Floskel-Marketing. Englisch nur dort, wo Fachbegriffe/Contracts es erfordern — dann konsistent.
3. **Inhalt:** Keine leeren Marketing-Phrasen; kompakt, aber handlungsrelevant (was bedeutet es für den Operator?).
4. **Interaktion:** Buttons und Links eindeutig benennen; keine toten Links; keine UI-Attrappen (keine Buttons ohne Wirkung oder ohne Fehlerfeedback).
5. **Responsive:** Layouts für Mobile und Desktop prüfen (Sidebar, Tabellen, Formulare).
6. **Architektur:** Nur notwendige Änderungen; bestehende Muster (BFF, `api.ts`, i18n-Keys) wiederverwenden; keine Secrets im Client.
7. **Dokumentation:** Wesentliche fachliche oder sicherheitsrelevante Änderungen kurz in bestehender Doku oder hier im Audit-Log ergänzen, wenn der Nutzer das verlangt.

---

## Wichtige Dateipfade (Referenz)

| Thema                | Pfade                                                                        |
| -------------------- | ---------------------------------------------------------------------------- |
| Routing / Layouts    | `apps/dashboard/src/app/**`, `middleware.ts`                                 |
| API-Client / Gateway | `apps/dashboard/src/lib/api.ts`, `gateway-bff.ts`, `server-env.ts`, `env.ts` |
| Navigation           | `components/layout/SidebarNav.tsx`, `FlowNavBar.tsx`, `lib/console-paths.ts` |
| Operator-Gates       | `ConsoleTelegramGate.tsx`, `lib/operator-session.ts`                         |
| BFF-Beispiele        | `apps/dashboard/src/app/api/dashboard/**/route.ts`                           |
| Python-Gateway & KI  | `services/api-gateway`, `services/llm-orchestrator`, `services/news-engine`  |
| Infrastruktur        | `docker-compose.yml`, `config/required_secrets_matrix.json`                  |

---

## Änderungshistorie (Audit-Datei)

| Datum      | Notiz                                                                                                                                              |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-04-02 | Erstaudit angelegt (Code-Review + Dashboard tsc/jest).                                                                                             |
| 2026-04-02 | Prompt 5: Signal-/News-/Marktuniversum-Filter i18n; Strategie-Status-Buttons übersetzt. Funktionsstand: `docs/dashboard-console-functionality.md`. |
| 2026-04-02 | Prompt 6: `lib/api.ts` Fehlerbehandlung/Timeouts/Logs; Live-BFF + Admin-Probe-Logging. Übersicht: `docs/api-status.md`.                            |
