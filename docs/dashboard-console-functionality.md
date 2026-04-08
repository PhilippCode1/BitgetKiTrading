# Dashboard-Konsole — Funktionsstand (Prompt 5)

**Stand:** 2026-04-02 (Codebasis `apps/dashboard`).  
Diese Datei ergänzt [`project-audit.md`](../project-audit.md) und beschreibt, was **wirklich angebunden** ist, was **bewusst abgeschaltet** ist und was **von externen Voraussetzungen** abhängt.

---

## Voll funktionsfähig (mit laufendem Gateway und korrekter ENV)

| Bereich                                                                          | Verhalten                                                                                                                                                                                     |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Signal-Center** (`/console/signals`)                                           | Filter über **Query-Strings** und **GET-Formular** für `playbook_id`; Daten über `fetchSignalsRecent` / Facets über `fetchSignalsFacets`. Alle sichtbaren Filterlabels sind **i18n** (DE/EN). |
| **News** (`/console/news`)                                                       | Filter `min_score` / `sentiment` per Link; Daten `fetchNewsScored`. Sentiment-Label und „alle“ **i18n**.                                                                                      |
| **Marktuniversum** (`/console/market-universe`)                                  | Snapshot, Konfiguration, Matrix-Tabelle, Instrument-Registry aus `fetchMarketUniverseStatus`; Texte **i18n**.                                                                                 |
| **Capability-Matrix** (`/console/capabilities`)                                  | Matrix aus Gateway-Daten; Verweis auf Marktuniversum.                                                                                                                                         |
| **Learning & Drift**                                                             | Mehrere parallele Gateway-Reads, Tabellen und Reports; überwiegend **i18n**.                                                                                                                  |
| **Ops, Terminal, Paper, Live-Broker, Approvals, Health, Usage, Account-Subtree** | Server-Fetch über `lib/api.ts` bzw. BFF `/api/dashboard/*`; Fehler- und Leerzustände sind im UI vorgesehen.                                                                                   |
| **Strategie-Detail — Lebenszyklus**                                              | `StrategyStatusActions` sendet **POST** an Proxy oder direktes Gateway (je nach `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY`); Button-Texte **i18n**.                                                 |
| **Admin Rules**                                                                  | Lesen/Schreiben über BFF oder Token-Modus; bei Ladefehler kein leeres Formular mehr ohne Hinweis.                                                                                             |
| **Einzahlung (Deposit)**                                                         | Echter Checkout-Flow inkl. **Mock-Abschluss** über `/api/.../mock-complete`, sofern Gateway und Secrets passen.                                                                               |
| **Telegram (Konto)**                                                             | Integrationen-API, Deep-Link, Test; Ladezustand im Panel.                                                                                                                                     |
| **Console Telegram Gate**                                                        | Optional `NEXT_PUBLIC_COMMERCIAL_TELEGRAM_REQUIRED`; leitet bei fehlender Verknüpfung zu `/console/account/telegram`.                                                                         |

---

## Bewusst deaktiviert oder eingeschränkt

| Mechanismus                                                   | Wirkung                                                                                                                     |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_ENABLE_ADMIN=false`                              | Strategie-Status-Buttons zeigen Hinweis, **keine** Mutation.                                                                |
| `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=false`                    | Admin/Strategie-Mutationen brauchen **X-Admin-Token** im Browser-Speicher — UI warnt (`strategyStatus`, `AdminRulesPanel`). |
| `resolveStrategyMutationsVisible()` / `resolveShowAdminNav()` | Blendet Admin-Navigation oder Schreibaktionen aus, wenn die Server-Session zum Gateway nicht reicht.                        |
| `NEXT_PUBLIC_COMMERCIAL_TELEGRAM_REQUIRED` (wenn gesetzt)     | Ohne Telegram nur noch Konto-Bereich der Konsole.                                                                           |

---

## Offen / abhängig von externen Voraussetzungen

| Thema                                            | Voraussetzung                                                                                                                                                        |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Alle Gateway-Daten**                           | Erreichbares **API-Gateway**, passende `API_GATEWAY_URL` / `DASHBOARD_GATEWAY_AUTHORIZATION` auf dem Dashboard-Server.                                               |
| **BFF-Commerce**                                 | Gateway-Module Commerce/Telegram aktiv; sonst 404/503 mit JSON-Hinweis.                                                                                              |
| **Mock-Zahlung**                                 | `PAYMENT_MOCK_WEBHOOK_SECRET` abgestimmt zwischen Dashboard und Gateway-Webhook.                                                                                     |
| **Stripe (Prod)**                                | Zusätzliche Produktions-ENV und getestete Stripe-Pfade (nicht Gegenstand dieser Prompt-5-Änderung).                                                                  |
| **Endkunden-Login**                              | Middleware steuert Locale + Onboarding; **kein** klassisches SaaS-Login in derselben Schicht — siehe Audit.                                                          |
| **Signal-Detailseite** (`/console/signals/[id]`) | Inhalt technisch umfangreich; viele **`<details>`-Summaries** sind noch **fest deutsch** (Fachfelder) — für vollständige Zweisprachigkeit weiteres i18n-Paket nötig. |
| **LLM / News-Anreicherung**                      | Läuft in Python-Services; Dashboard zeigt nur, was das Gateway liefert.                                                                                              |

---

## Änderungen in Prompt 5 (Kurz)

- **Signal-Filter:** Keine optischen Platzhalter mehr — Formular nutzt Theme-Klassen `console-filter-input` / `console-filter-submit`; Texte unter `pages.signals.filters.*`.
- **Marktuniversum & News:** Hardcodierte UI-Strings durch **messages** ersetzt.
- **Strategie-Admin-Buttons:** Beschriftungen unter `strategyStatus.action*`.

Weitere technische Stabilität (Error Boundaries, Loading, SSE-Härtung) siehe vorherige Prompts und `project-audit.md`.
