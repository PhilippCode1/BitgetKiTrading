# Repo-Wahrheit und verbindliche Abschlussdefinition (bitget-btc-ai)

**Dokumenttyp:** Harte Ist-Beschreibung, ehrliche Verifikationsmatrix, **Definition of Done** mit messbaren „grün“-Kriterien.  
**Gültig ab:** 2026-04-05.  
**Quellen:** `docs/chatgpt_handoff/01`–`09` (vollständig gelesen), direkter Repo-Abgleich, **frische Verifikationsläufe** auf Windows/PowerShell im Repo-Root (siehe Abschnitt 11).

---

## 1. Zweck

Dieses Dokument ist die **verbindliche Wahrheitsgrundlage**: Was im Code und in Compose **existiert**, was nur **vorbereitet** ist, was **nachweislich kaputt oder rot** ist, und wann das Projekt **fertig** ist — ausschließlich über **benannte, wiederholbare Prüfungen**, nicht über vage Begriffe wie „stabil“ oder „reif“.

---

## 2. Globale Regeln aus den Übergabedateien (01–09) — Anwendung

| Regel / Prinzip                                                                  | Herkunft       | operative Konsequenz für dieses Projekt                                                                   |
| -------------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------- |
| **Evidenz-Trennung** (verifiziert / abgeleitet / nicht verifiziert)              | 01, 05, 06, 09 | Jede Statusaussage im Team muss mit Prüfart oder Dateipfad belegt sein.                                   |
| **Compose = Kanon** für Topologie und Startreihenfolge                           | 02             | Abweichungen von Doku nur nach `docker-compose.yml` + `infra/service-manifest.yaml`.                      |
| **Zwei Keys** (`GATEWAY_INTERNAL_API_KEY` vs. `INTERNAL_API_KEY`)                | 03             | Nie vermischen; Diagnose über `edge-status` + Logs.                                                       |
| **BFF vs. Gateway-Pfade**                                                        | 04             | Browser → `/api/dashboard/*` → Gateway `/v1/*`; Postgres-Lesepfade oft **im Gateway**, nicht Worker-HTTP. |
| **Kerzen = `tsdb.candles`**, Shadow kein eigener Feed                            | 05             | Leere Charts zuerst an Pipeline/Frische, nicht an „Chart-Bug“ delegieren.                                 |
| **Kein LLM-Trading**; `execution_authority: none` auf den zwei Haupt-KI-Strecken | 06             | Keine Marketing-Aussagen „KI handelt“.                                                                    |
| **UX/Sprache:** Profi vs. einfache Ansicht; Screenshots fehlen                   | 07             | Release ohne dokumentierte visuelle Beweise = **nicht bewiesen**.                                         |
| **Fehler-Priorität P0/P1/P2**                                                    | 08             | Erst Infra/Auth/DB, dann Datenpipeline, dann UX.                                                          |
| **Session-Beweise aus 09 + Re-Check 2026-04-05**                                 | 09, §11 hier   | Typecheck/Format/Selfcheck/Smoke: **rot** bis Gegenbeweis.                                                |

---

## 3. Harte Ist-Analyse — Was ist wirklich implementiert

**verifiziert (Repo-Struktur + Code):**

- **Monorepo:** Next.js-Dashboard (`apps/dashboard`), Python-Services unter `services/*` mit `pyproject.toml`, `shared/python` (`shared_py`), `shared/ts`, `shared/contracts/`.
- **Laufzeit-Kette:** `docker-compose.yml` mit Postgres, Redis, migrate, market-stream → feature/structure/drawing → llm-orchestrator → news-engine → signal-engine → paper-broker → live-broker → learning-engine → alert-engine → api-gateway → dashboard; optional `monitor-engine`; Profil `observability` für Prometheus/Grafana.
- **API-Gateway:** FastAPI mit `/health`, `/ready`, `/v1/*` (Proxys lesen überwiegend **PostgreSQL** im Gateway-Prozess); LLM- und Live-Broker-Mutationen über **HTTP-Forward** mit `X-Internal-Service-Key`.
- **Dashboard-BFF:** `apps/dashboard/src/app/api/dashboard/*` mit `DASHBOARD_GATEWAY_AUTHORIZATION` serverseitig.
- **Deterministischer Signal-Kern:** signal-engine + Shared-Module; ADR-0001 „kein LLM-only-Trading“.
- **LLM:** llm-orchestrator mit strukturierten Endpunkten; Gateway `/v1/llm/operator/*`, `/v1/llm/assist/*`; BFF für Operator-Explain, Strategy-Signal-Explain, Assist-Segmente.
- **Datenfluss Markt → UI:** `GET /v1/live/state`, optional SSE `/v1/live/stream` (Redis); Charts aus `tsdb.candles`.
- **Migrations:** **85** SQL-Dateien unter `infra/migrations/postgres/` (Stand Zählung 2026-04-05).
- **CI:** `.github/workflows/ci.yml` — Python (Ruff, Black, Mypy, Pytest, …), Dashboard-Job, Compose-Health (laut Workflow-Kommentar).
- **Qualitätsskripte:** `tools/production_selfcheck.py`, `scripts/release_gate.py`, `scripts/api_integration_smoke.py`, `e2e/tests/release-gate.spec.ts`, `scripts/healthcheck.sh` (Bash).

---

## 4. Was ist nur vorbereitet oder fragmentarisch

**verifiziert (Doku/Code-Hinweise, keine vollständige Produktreife behauptet):**

- **Multi-Instrument-/Family-Orchestrierung, replay-stabile Event-Metadaten, family-neutrale Registry:** laut `docs/REPO_TRUTH_MATRIX.md` / `PRODUCT_STATUS.md` **teilweise** — nicht als „fertig“ verkaufen.
- **Grafana-Dashboards:** Assets existieren; „ausgefüllt/produktreif“ in Matrix **offen**.
- **OpenAPI vs. Runtime:** `shared/contracts/openapi/api-gateway.openapi.json` — **keine** laufende Paritätsprüfung in diesem Dokument belegt.
- **Commerce/Zahlung:** Migrationen und Routen vorhanden; End-to-End-Zahlungsbetrieb **ohne Staging-Evidenz** nicht bewiesen.
- **Screenshot-Regression:** `docs/Cursor/assets/screenshots/` — laut Handoff 07 im Wesentlichen leer (Platzhalter); **kein** visueller Release-Nachweis.

---

## 5. Was ist nachweislich kaputt oder rot (lokal, 2026-04-05)

**verifiziert (Befehle ausgeführt, Exit ≠ 0):**

| Prüfung                                | Ergebnis          | Kurzursache                                                                                                                                  |
| -------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm check-types`                     | **FAIL**          | `admin/page.tsx`: `SystemHealthResponse` ohne `status`; `paper/page.tsx`: `account_ledger_recent` optional vs. required.                     |
| `pnpm format:check`                    | **FAIL (Exit 2)** | Prettier **SyntaxError** auf `.github/workflows/ci.yml` („Nested mappings…“ bei Zeile ~71); dazu sehr viele `[warn]`-Dateien.                |
| `python tools/production_selfcheck.py` | **FAIL**          | Ruff **E501** in `tools/production_selfcheck.py:221` (Zeile zu lang).                                                                        |
| `pnpm smoke` → `scripts/rc_health.ps1` | **FAIL**          | **ParserError** in `scripts/_dev_compose.ps1`: UTF-8/Em-Dash in Strings wird als `?` interpretiert → String bricht vor `bitte` / `JWT-Mint`. |

**abgeleitet:** Solange diese vier Punkte rot sind, ist **`pnpm release:gate`** und jede Aussage „Release-ready“ **unbelegt**.

---

## 6. Was ist dokumentiert, aber nicht bewiesen

| Thema                                               | Dokumentation                                                           | Warum „nicht bewiesen“                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Vollständiger Docker-Stack healthy                  | `docs/stack_readiness.md`, README                                       | Kein grüner `docker compose ps` + `/ready`-Export in dieser Session.  |
| Gateway-`/v1/system/health` mit realem Operator-JWT | API-Dossier                                                             | Kein authentifizierter Lauf dokumentiert.                             |
| Playwright E2E                                      | `e2e/tests/release-gate.spec.ts`                                        | `pnpm e2e` hier **nicht** ausgeführt.                                 |
| Bash-Smokes                                         | `scripts/healthcheck.sh`, `tests/dashboard/test_live_state_contract.sh` | Nicht auf Windows ohne WSL/Bash belegt.                               |
| Bitget **private** REST mit Keys                    | Tools unter `bitget:verify:*`                                           | Öffentlicher Tickers-Call (Handoff 09) beweist nicht Trading-Kontext. |
| „Alle Engines liefern Frische“                      | Pipeline-Doku                                                           | Braucht laufende Container + Logs.                                    |

---

## 7. Paper, Shadow, Live — aktueller Stand (logisch, Repo-konform)

| Modus      | Bedeutung im Repo                                                                                                        | Implementiert (technisch)                  | Bewiesen (Laufzeit)                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------- |
| **Paper**  | `EXECUTION_MODE=paper`, Portfolio/Journal in `paper.*`, API `/v1/paper/*`                                                | **Ja** — Services und Routen vorhanden     | **Nein** — kein grüner Stack-Nachweis hier                    |
| **Shadow** | `EXECUTION_MODE=shadow`, Simulation ohne Live-Submit; Vergleichssichten über Live-Broker + Paper (`console/shadow-live`) | **Ja** — Codepfade und Seiten              | **Nein** — kein Shadow-Staging-Lauf dokumentiert              |
| **Live**   | `EXECUTION_MODE=live`, live-broker, Safety-Gates, Bitget-Keys                                                            | **Ja** — Control-Plane und Exchange-Client | **Nein** — kein Live-Handelsnachweis; **absichtlich** gegatet |

---

## 8. Liste „verifiziert / offen / nicht bewiesen“ (Kurzfassung)

### 8.1 Verifiziert (Struktur oder gezielter Testlauf)

- Compose-Serviceliste und Abhängigkeitsgraph (aus `docker-compose.yml`).
- Gateway-/BFF-Architektur und LLM-Pfad-Dateien (Handoff 04, 06).
- Anzahl SQL-Migrationen: **85**.
- **2026-04-05:** `pnpm check-types` schlägt mit **2 TS-Fehlern** fehl (siehe §5).
- **2026-04-05:** `pnpm format:check` schlägt mit **ci.yml-Parserfehler** fehl.
- **2026-04-05:** `production_selfcheck.py` schlägt an **Ruff E501** fehl.
- **2026-04-05:** `pnpm smoke` schlägt an **PowerShell-Parser** in `_dev_compose.ps1` fehl.
- Handoff 09 + 06: ausgewählte **Pytest/Jest**-Suiten waren an 2026-04-04 grün (isolierter Kontext) — **kein** Ersatz für Stack-E2E.

### 8.2 Offen (muss für „fertig“ geschlossen werden)

- Typecheck, Format, Ruff-Selfcheck, Windows-Smoke reparieren und **grün** dokumentieren.
- `ci.yml` so formatieren/ignorieren, dass Prettier **nicht** mit YAML-Parser bricht **oder** CI-Datei aus Prettier-Scope mit dokumentierter Begründung.
- Vollständiger Stack-Start + Gateway `/ready` + `/v1/system/health` (mit JWT) + `api_integration_smoke.py` Exit 0.
- `pnpm e2e` bzw. `release_gate.py --with-e2e` grün.
- Screenshot-Set mit Datum in `docs/Cursor/assets/screenshots/` (oder vereinbarter Pfad) für kritische UI-Flows.

### 8.3 Nicht bewiesen (keine Behauptung „funktioniert“ ohne neue Evidenz)

- Produktions- oder Shadow-Deployment auf Ziel-Infra.
- Erfolgreicher **echter** Live-Order-Flow (und soll bis zur organisatorischen Freigabe **nicht** als Standardnachweis gelten).
- Vollständige Observability-Nutzung (Grafana inhaltlich gefüllt).
- Parität OpenAPI ↔ Code.

---

## 9. Verbindliche Definition of Done (Projekt = „fertig“)

Die Anwendung gilt **erst dann** als **fertig**, wenn **alle** folgenden Prüfungen **dokumentiert grün** sind (Log-Auszug, CI-Run-URL, oder Anhang mit Zeitstempel und Commit-SHA):

### 9.1 Build und Frontend-Qualität

1. **`pnpm build`** — Exit 0 (Turbo `build` für Dashboard und abhängige Pakete).
2. **`pnpm check-types`** — Exit 0 (`tsc --noEmit` im Dashboard; shared-ts wie in Turbo definiert).
3. **`pnpm lint`** — Exit 0 (Turbo `lint`, alle Workspace-Pakete mit Lint-Skript).

### 9.2 Format

4. **`pnpm format:check`** — Exit 0 **oder** dokumentierte, teamverbindliche Alternative (z. B. eingeschränkter Prettier-Glob), mit Begründung im PR — **ohne** dass `.github/workflows/ci.yml` den Parser bricht.

### 9.3 Relevante Python-Checks (lokal CI-äquivalent)

5. **`python tools/production_selfcheck.py`** — Exit 0 (inkl. Ruff/Black/Mypy-Pfade wie im Skript; optional mit gesetzter `DATABASE_URL` für DB-Gates).
6. **CI-Python-Subset** wie in `.github/workflows/ci.yml` Job `python` (Ruff/Black/Mypy/Pytest-Scopes) — Exit 0, nachvollziehbar dokumentiert (lokal oder GitHub Actions Run).

### 9.4 Stack-Start und Health

7. **Stack-Start** — z. B. `pnpm dev:up` oder dokumentiertes Compose-Äquivalent mit `COMPOSE_ENV_FILE` — Exit 0; alle für das Profil erwarteten Container **healthy** (Auszug `docker compose ps`).
8. **Gateway-Readiness** — `GET http://<gateway-host>:8000/ready` → HTTP 200, JSON mit `ready: true` (exakter Schlüssel wie Gateway-Implementierung).
9. **System-Health** — `GET http://<gateway-host>:8000/v1/system/health` mit **gültigem** Operator-/Aggregate-JWT → HTTP 200 und strukturierte Payload ohne `database`/`redis` auf hartem Fehlerzustand für das Zielprofil.

### 9.5 API-Smoke

10. **`python scripts/api_integration_smoke.py`** — Exit 0 gegen die **laufende** Gateway-URL aus `.env.local` (inkl. erfolgreicher Gateway-Schritte, nicht nur öffentlicher Bitget-Schritt).

### 9.6 E2E

11. **`pnpm e2e`** — Exit 0 mit `e2e/playwright.config.ts`, Basis-URL dokumentiert; mindestens `e2e/tests/release-gate.spec.ts` vollständig grün.

### 9.7 Kritische UI-Flows (manuell oder E2E-abgedeckt)

12. Nachweis, dass **alle** folgenden Routen **ohne** `main .msg-err` und **ohne** `main .console-fetch-notice--alert` laden (wie Release-Gate-Spezifikation) **oder** E2E-Äquivalent:  
    `/`, `/console/health`, `/console/integrations`, `/console/signals`, `/console/learning`, `/console/live-broker`, `/console/approvals`, `/console/ops`, `/console/usage`, `/console/account`, `/console/account/broker`, `/console/terminal` (inkl. Chart-Toolbar-Expectations laut Spec).

### 9.8 KI-Flows

13. **BFF Operator-Explain** — `POST /api/dashboard/llm/operator-explain` mit Testfrage → HTTP 2xx, `explanation_de` nicht leer (Release-Gate-Test spiegelt das).
14. **Strategie-Signal-Explain** — `POST /api/dashboard/llm/strategy-signal-explain` mit gültigem Body → HTTP 2xx und schema-konformes Ergebnis (gezielter Test oder manueller Nachweis).
15. **Optional erweitert:** `scripts/verify_ai_operator_explain.py` im Modus `orchestrator` wie in `release_gate.py` — Exit 0.

### 9.9 Screenshot-Beweise

16. Mindestens **10** Screenshots (Desktop + Mobile gemischt, definierte Liste in `00_master_execution_plan.md`) unter `docs/Cursor/assets/screenshots/` mit **Datumspräfix** im Dateinamen und `README.md` im selben Ordner mit Zuordnung URL → Datei → Commit.

### 9.10 Release-Gate Gesamt

17. **`python scripts/release_gate.py --with-e2e`** — Exit 0 auf dem Zielrechner/CI mit **nicht** gesetzten Skip-ENVs (`SKIP_STACK_SMOKES`, `SKIP_DASHBOARD_PROBE`), sofern Stack und Dashboard erreichbar.

---

## 10. Zielzustand 10 von 10 (Kurz)

**10/10** bedeutet: **§9 vollständig grün**, plus **keine** bekannten P0-Items in der Gap-Matrix (`00_master_execution_plan.md`), plus **ehrliche** Kennzeichnung aller nicht bewiesenen organisatorischen Go-Live-Punkte (`docs/LAUNCH_DOSSIER.md` etc.) als **außerhalb Repo**.

---

## 11. Anhang: Verifikationsläufe 2026-04-05 (Windows)

| Kommando                               | Exit | Wesentliche Ausgabe                                                                    |
| -------------------------------------- | ---- | -------------------------------------------------------------------------------------- |
| `pnpm check-types`                     | 1    | TS2339 `admin/page.tsx` (`status`); TS2322 `paper/page.tsx` (`account_ledger_recent`). |
| `pnpm format:check`                    | 2    | Prettier SyntaxError `.github/workflows/ci.yml:71`.                                    |
| `python tools/production_selfcheck.py` | 1    | Ruff E501 `tools/production_selfcheck.py:221`.                                         |
| `pnpm smoke`                           | 1    | ParserError `scripts/_dev_compose.ps1:37` / `:73` (Encoding).                          |

---

## 12. Pfad-Index

| Thema                           | Pfad                                                     |
| ------------------------------- | -------------------------------------------------------- |
| Handoff-Paket                   | `docs/chatgpt_handoff/01`–`09`                           |
| Master-Reihenfolge & 49 Prompts | `docs/cursor_execution/00_master_execution_plan.md`      |
| Compose                         | `docker-compose.yml`, `docker-compose.local-publish.yml` |
| Release-Gate                    | `scripts/release_gate.py`                                |
| E2E                             | `e2e/tests/release-gate.spec.ts`                         |
| Ist-Matrix (älterer Freeze)     | `docs/REPO_TRUTH_MATRIX.md`                              |

---

_Ende der Datei._
