# bitget-btc-ai — Gesamtüberblick (ChatGPT-Übergabe)

**Dokumenttyp:** Einsteiger-Handoff für externe technische Partner.  
**Stand (Repo-Analyse):** 2026-04-04.  
**Evidenzlogik:** Aussagen sind mit **verifiziert** (direkt im Code/Compose/Dateibaum belegt), **abgeleitet** (aus Repo-Doku/Architekturtexten geschlossen) oder **nicht verifiziert** (keine ausreichende Repo-Evidenz) markiert.

---

## 1. Projekttitel und Kurzdefinition

**Titel:** _Bitget Marktuniversum KI_ (Repo-Name: `bitget-btc-ai`). **verifiziert:** `README.md` (Kopfzeile und Projektname).

**Kurzdefinition:** Monorepo für eine **metadata-getriebene** Handels- und Analyseplattform rund um **Bitget** (Spot, Margin, Futures-Familien): Marktdaten → Feature-/Struktur-/Drawing-Pipeline → **deterministischer Signal-Kern** (Risk, Gating, Playbooks) → Ausführung über **Paper**, **Shadow** oder **operator-gated Live** via **Live-Broker**. **LLM** ist **unterstützend** (Erklärungen, News-Anreicherung, strukturierte Analystenaufgaben), **nicht** der alleinige Trading-Kern. **verifiziert:** `README.md`, `docs/adr/ADR-0001-bitget-market-universe-platform.md` (Entscheidung „Kein LLM-only-Trading“).

---

## 2. Geschäftlicher Zweck des Systems

**Zielbild (abgeleitet aus Doku):** Bereitstellung einer **betreibbaren Software- und Doku-Basis** für ein professionelles Markt-/Risiko-/Ausführungs-Setup mit klar getrennten Modi (Paper/Shadow/Live), Operator-Sichten und nachvollziehbaren Grenzen — **ohne** implizite Go-Live-Garantie. **abgeleitet:** `PRODUCT_STATUS.md`, `docs/LAUNCH_DOSSIER.md` (Verweis in `README.md`).

**Kommerzielle Bausteine (technisch im Repo angelegt):** Pläne, Entitlements, Usage-Metering, Abrechnungs-/Ledger-Migrationen werden in `docs/PRODUCT_PLANS_AND_USAGE.md` und zugehörigen SQL-Migrationen beschrieben (z. B. `infra/migrations/postgres/594_commercial_usage_entitlements.sql`, weitere `60x_*.sql`). **verifiziert:** genannte Dateien existieren; **abgeleitet:** tatsächlicher externer Zahlungs-/Vertragsprozess und Marktlaunch sind organisatorisch und nicht allein aus dem Repo ableitbar.

**Produkt-/Compliance-Rahmen:** ADR und Runbooks betonen: Chat/Telegram **kein** Kanal für Strategie-Mutation; Live bleibt **gegatet**. **verifiziert:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`.

---

## 3. Technischer Zweck des Systems

1. **Daten- und Entscheidungspipeline:** Kontinuierliche Verarbeitung von Bitget-Marktdaten, Ableitung von Features, Struktur und Zeichnungen, deterministische Signalerzeugung und nachgelagerte Broker-Logik. **verifiziert:** `docker-compose.yml` (Service-Kette `market-stream` → … → `signal-engine` → `paper-broker` / `live-broker`), `infra/service-manifest.yaml`.
2. **Kontrollierte Ausführung:** Paper als Referenz, Shadow als produktionsnahe Simulation ohne Live-Submit, Live nur mit expliziten Freigaben und Safety-Gates. **verifiziert:** `README.md` (Kernregeln), `docs/REPO_TRUTH_MATRIX.md` (Betriebsmodi-Tabelle).
3. **Edge-API und UI:** Zentrales **API-Gateway** (HTTP/Ready/Aggregation) und **Next.js-Dashboard** für Operator:innen (Lesepfade, Signale, Ops, Health, Broker-Sichten). **verifiziert:** `services/api-gateway/`, `apps/dashboard/`, `docker-compose.yml` (`api-gateway`, `dashboard`).
4. **Observability-Option:** Prometheus/Grafana als **Compose-Profil** `observability`, nicht Teil des schlanken Basis-Stacks. **verifiziert:** `docker-compose.yml` (`profiles: observability`).

---

## 4. Hauptkomponenten des Monorepos

| Bereich             | Inhalt                                                                                           | Evidenz                                                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| **Apps**            | Eine produktive Next.js-App `@bitget-btc-ai/dashboard` (Next 16, React 19, Standalone-Build).    | **verifiziert:** `apps/dashboard/package.json`, `README.md`                                                              |
| **Python-Services** | 13 Services mit je `pyproject.toml` unter `services/*`.                                          | **verifiziert:** Glob `services/*/pyproject.toml`                                                                        |
| **Shared Runtime**  | `shared/python` (`shared_py`), `shared/ts` (`@bitget-btc-ai/shared-ts`), zentrale `config/`.     | **verifiziert:** Verzeichnisstruktur, `apps/dashboard/package.json` workspace-Abhängigkeit                               |
| **Verträge**        | JSON-Schemas, Event-Katalog, OpenAPI u. a. unter `shared/contracts/`.                            | **verifiziert:** Verzeichnis `shared/contracts/`                                                                         |
| **Infra**           | Postgres-Migrationen, Dockerfiles, Compose, Observability-Assets, `infra/service-manifest.yaml`. | **verifiziert:** `infra/migrations/postgres/*.sql` (aktuell **85** Dateien, Stand Zählung im Repo), `docker-compose.yml` |
| **Tests**           | `tests/`, `shared/python/tests/`, Dashboard-Jest, Playwright unter `e2e/`.                       | **verifiziert:** Verzeichnisse, `package.json` Skripte `e2e`, `apps/dashboard` Jest                                      |
| **Tooling**         | `tools/` (Selfchecks, Validierung), `scripts/` (Bootstrap, Health, Release-Gate).                | **verifiziert:** `package.json` ruft u. a. `python tools/production_selfcheck.py`, `scripts/*.ps1` auf                   |
| **CI**              | GitHub Actions Workflow `ci` (Python, Schema, Compose-Health, Dashboard, u. a.).                 | **verifiziert:** `.github/workflows/ci.yml`                                                                              |

---

## 5. Welche Nutzeroberflächen existieren

**Eine** primäre Web-UI: **Dashboard** (`apps/dashboard`), App-Router unter `apps/dashboard/src/app/`.

**Verifiziert vorhandene Routen (Auszug aus Dateibaum):**

- Öffentlich: `/(public)/page.tsx`, Onboarding/Welcome.
- Operator-Konsole unter `/(operator)/console/`: u. a. **Signale** (`console/signals`, `console/signals/[id]`), **Ops** (`console/ops`), **Health** (`console/health`), **Terminal**, **Paper**, **Live-Broker**, **Shadow/Live**, **News**, **Strategien**, **Learning**, **Market Universe**, **Capabilities**, **No-Trade**, **Approvals**, **Integrations**, **Usage**, **Account-** und **Admin-**Zweige (Kunden, Billing, Commerce, Telegram, AI-Governance, …).

**Architekturhinweis:** Dashboard nutzt **BFF**-Routen `apps/dashboard` → `/api/dashboard/*` und serverseitige Gateway-Auth (`DASHBOARD_GATEWAY_AUTHORIZATION`). **verifiziert:** `ai-architecture.md`, `API_INTEGRATION_STATUS.md`.

**Lesend / keine Strategie-Mutation aus dem Browser:** laut Root-README für Signal-Center und Operator-Cockpit. **abgeleitet:** `README.md` (Abschnitt Repository Structure).

---

## 6. Welche Backend-Dienste existieren

**In `docker-compose.yml` als Laufzeit-Services definiert (verifiziert):**

| Service                 | Rolle (kurz)                                                   |
| ----------------------- | -------------------------------------------------------------- |
| `postgres`, `redis`     | Persistenz, Streams/Cache                                      |
| `migrate`               | DB-Migrationen beim Start                                      |
| `market-stream`         | Bitget WS/REST, Feed-Health                                    |
| `feature-engine`        | Features                                                       |
| `structure-engine`      | Marktstruktur                                                  |
| `drawing-engine`        | Drawings/Zonen (abhängig von structure)                        |
| `news-engine`           | News-Ingest/Scoring; Readiness abhängig von `llm-orchestrator` |
| `llm-orchestrator`      | Strukturierte LLM-Endpunkte (intern gehärtet)                  |
| `signal-engine`         | Deterministischer Signal-Kern                                  |
| `paper-broker`          | Paper-Ausführung                                               |
| `learning-engine`       | Registry/Backtest/Drift (u. a. Volume für Artefakte)           |
| `live-broker`           | Control-Plane / Exchange-Ausführung                            |
| `alert-engine`          | Alerts/Telegram/Outbox                                         |
| `monitor-engine`        | Monitoring-Worker (u. a. `MONITOR_SERVICE_URLS`)               |
| `api-gateway`           | Edge HTTP :8000                                                |
| `dashboard`             | Next.js :3000                                                  |
| `prometheus`, `grafana` | optional, Profil `observability`                               |

**Entrypoints und Pflicht-ENV:** maschinenlesbar in `infra/service-manifest.yaml`. **verifiziert.**

**Ob alle Logikpfade in jedem Modus vollständig „fertig“ sind:** siehe Abschnitt 9 und `docs/REPO_TRUTH_MATRIX.md` (Lückenliste).

---

## 7. Welche externen Integrationen existieren

| Integration                  | Wo im Repo sichtbar                                                  | Status                                                                                                                                                      |
| ---------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Bitget** (REST/WebSocket)  | `market-stream`, `live-broker`, Shared `shared_py.bitget`            | **verifiziert:** Compose, Pakete, `API_INTEGRATION_STATUS.md`                                                                                               |
| **OpenAI**                   | `llm-orchestrator` (`OPENAI_API_KEY`); Fake: `LLM_USE_FAKE_PROVIDER` | **verifiziert:** `services/llm-orchestrator`, `ai-architecture.md`                                                                                          |
| **PostgreSQL / Redis**       | Alle Kern-Services                                                   | **verifiziert:** `docker-compose.yml`                                                                                                                       |
| **Telegram**                 | `alert-engine`, Doku/ENV                                             | **verifiziert:** `API_INTEGRATION_STATUS.md`, Compose-Service `alert-engine`                                                                                |
| **News-Quellen**             | `news-engine`, `NEWS_*`, `NEWS_FIXTURE_MODE`                         | **verifiziert:** `API_INTEGRATION_STATUS.md`, `services/news-engine`                                                                                        |
| **Zahlungs-/Commerce-Pfade** | Gateway `/v1/commerce/*`, Migrationen 598–610 u. a.                  | **verifiziert:** Routen in Doku `API_INTEGRATION_STATUS.md`; End-to-End-Produktreife **abgeleitet/nicht verifiziert** ohne laufende Staging-Evidenz im Repo |

---

## 8. Welche KI-Funktionen nachweislich existieren

### 8.1 LLM-Orchestrator (interne HTTP-API)

**verifiziert** in `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`:

- `POST /llm/structured` — generisches strukturiertes JSON-Schema-Calling
- `POST /llm/news_summary` — News-Zusammenfassung
- `POST /llm/analyst/hypotheses`, `…/context_classification`, `…/post_trade_review`
- `POST /llm/analyst/operator_explain`, `…/strategy_signal_explain`, `…/strategy_journal_summary`
- `POST /llm/assist/turn` — Assistenz mit Rollen und `conversation_id`
- `GET /llm/governance/summary`  
  Alle sensiblen Pfade: `InternalServiceAuthContext` (**verifiziert:** `build_internal_service_dependency` in derselben Datei).

### 8.2 End-to-End bis Dashboard (Gateway + BFF)

**Zwei** vom Produkt explizit als „echte LLM-Strecke“ für das Dashboard beschriebene Pfade: **verifiziert** `PRODUCT_STATUS.md`, `ai-architecture.md`:

1. **Operator Explain:** UI `console/health` → BFF → Gateway `POST /v1/llm/operator/explain` → Orchestrator `POST /llm/analyst/operator_explain`.
2. **Strategie-/Signalerklärung:** UI `console/signals/[id]` → BFF → Gateway `POST /v1/llm/operator/strategy-signal-explain` → Orchestrator `POST /llm/analyst/strategy_signal_explain`.

**Tests (verifiziert, Stichworte):** `tests/unit/api_gateway/test_routes_llm_operator.py`, `tests/llm_orchestrator/*`, Dashboard-Jest-Dateien laut `PRODUCT_STATUS.md` / `ai-architecture.md`.

### 8.3 News-Engine + LLM

**verifiziert:** `services/news-engine/src/news_engine/scoring/llm_enricher.py` ruft den Orchestrator (`/llm/news_summary`) auf; Logik ist mit Regel-Scores und Clamp kombiniert („Handelslogik nicht ausschließlich auf LLM“ — im Dateikommentar dokumentiert).

### 8.4 Trading-Kern

**Deterministische** Signal- und Risk-Logik im **signal-engine** und Shared-Modulen — **kein** LLM als Order-Entscheider laut ADR/README. **verifiziert:** ADR-0001, `README.md`.

---

## 9. Was noch nicht vollständig gebaut ist

**Aus `docs/REPO_TRUTH_MATRIX.md` (verifiziert als Repo-„Freeze“-Befund, Stand dort 2026-03-30):**

- **Family-weite Multi-Instrument-Orchestrierung:** nur teilweise; Laufzeit überwiegend single-instrument pro Serviceinstanz trotz Katalog/Metadaten-Layer.
- **Vollständig replay-stabile Event-Metadaten:** nein (`shared_py.eventbus.envelope` referenziert).
- **Family-neutrale Registry ohne BTC-Defaults:** teilweise.
- **Dashboard-/Gateway-Contract-Abdeckung:** teilweise (`shared/contracts/openapi/…`, `shared/ts`).
- **Ausgefüllte Grafana-Dashboards:** nein (Platzhalter laut Matrix).

**Aus `PRODUCT_STATUS.md` (verifiziert):**

- **Voller Produktionsbetrieb** abhängig von Secrets, Exchange, Compliance, Freigaben — nicht automatisch durch Repo allein.
- **KI jenseits der zwei Dashboard-Pfade:** weitere Orchestrator-Endpunkte nicht alle an Gateway+BFF angebunden.
- **Persistenter Multi-Turn-Chat** für den Operator-Assistenten: bewusst nicht gebaut.
- **CI/ENV:** volle Gateway-`create_app()`-Tests brauchen konsistente Pflicht-ENV.

**Zielarchitektur vs. Code:** ADR-0001 beschreibt den **Soll-Zustand**; die Matrix explizit: bei Widerspruch gilt Laufzeitstand aus Code/Compose. **abgeleitet:** `docs/REPO_TRUTH_MATRIX.md` Einleitung.

---

## 10. Was aktuell produktionsnah wirkt

**verifiziert (Repo-Artefakte):**

- Vollständiger **Docker-Compose**-Stack mit Healthchecks und Abhängigkeitsketten (`docker-compose.yml`).
- **API-Gateway** mit `/ready`-Aggregation über Worker-URLs (`HEALTH_URL_*`).
- **CI-Workflow** inkl. Compose- und KI-Orchestrator-Smoke (Kommentarkopf `.github/workflows/ci.yml`).
- **Release-/Selfcheck-Tooling:** `tools/production_selfcheck.py`, `scripts/release_gate.py`, `pnpm release:gate` / `release:gate:full`.
- **Sicherheits- und Betriebsdoku:** `docs/api_gateway_security.md`, `docs/Deploy.md`, `docs/prod_runbook.md` (genannt in `README.md`).
- **E2E Playwright:** `e2e/playwright.config.ts`, Skript `pnpm e2e`; laut `PRODUCT_STATUS.md` Kernpfade in CI-Job `compose_healthcheck`.

**abgeleitet:** „Produktionsnah“ bedeutet hier **technische Reife der Software-Artefakte**, nicht automatisch erfolgten Live-Handel oder marktfertiges SaaS-Betriebsmodell — siehe `PRODUCT_STATUS.md` / `docs/LAUNCH_DOSSIER.md`.

---

## 11. Wichtigste Risiken

1. **Live-Handel / Exchange-Fehler / API-Änderungen Bitget** — finanzielles und operatives Risiko bei falscher Konfiguration. **abgeleitet:** Domäne + `live-broker`; **nicht verifiziert:** konkrete Bitget-API-Version zum Analysezeitpunkt.
2. **Secrets und ENV-Drift** — `INTERNAL_API_KEY`, `DASHBOARD_GATEWAY_AUTHORIZATION`, `HEALTH_URL_*` (Docker vs. Host). **verifiziert:** `API_INTEGRATION_STATUS.md` (Fehlerursachen-Tabelle).
3. **LLM-Kosten und Ausfall** — ohne `OPENAI_API_KEY` bzw. mit Provider-Ausfall 502/503; Fake nur für Tests erlaubt. **verifiziert:** `ai-architecture.md`, `config`-Validierung (Prod-Verbote laut Doku).
4. **Dokumentationsalter** — einzelne `docs/*` können hinter dem Code stehen; Matrix nennt das explizit. **verifiziert:** `PRODUCT_STATUS.md`, `docs/REPO_TRUTH_MATRIX.md`.
5. **Single-Host-/Compose-Annahmen** — Skalierung und HA sind nicht aus diesem einen Compose-File ablesbar. **abgeleitet.**

---

## 12. Wichtigste offene Lücken

- **Governance von „metadata-first“ über alle Events/UI** bis replay-stabil — laut Matrix unvollständig. **verifiziert:** `docs/REPO_TRUTH_MATRIX.md`.
- **Endnutzer-Anbindung aller LLM-Fähigkeiten** — Orchestrator bietet mehr Routen als das Dashboard öffentlich nutzt. **verifiziert:** Vergleich `routes.py` vs. `PRODUCT_STATUS.md`.
- **Observability-Tiefe** — Grafana-Dashboards und ggf. LLM-Latenz-Metriken als Produktpflicht: laut Produkt-Backlog in `PRODUCT_STATUS.md` / Matrix offen.
- **Organisatorisches Go-Live** — Checklisten und Dossiers existieren (`docs/LaunchChecklist.md`, `docs/LAUNCH_DOSSIER.md`); deren Abhaken ist **nicht verifiziert** im Repo-Zustand.
- **Migrationszahl in älteren Doku-Snapshots:** `REPO_TRUTH_MATRIX.md` nennt „65“ Migrationen; aktueller Baum zählt **85** `.sql`-Dateien unter `infra/migrations/postgres/` — **verifiziert** Zählung; **abgeleitet:** Matrix-Abschnitt teilweise veraltet.

---

## 13. Dateipfade und wichtigste Startpunkte im Repo

| Zweck                        | Pfad                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Projektüberblick, Quickstart | `README.md`, `LOCAL_START_MINIMUM.md`, `docs/LOCAL_START_MINIMUM.md`                                         |
| Zielarchitektur              | `docs/adr/ADR-0001-bitget-market-universe-platform.md`                                                       |
| Ist-/Freeze-Matrix           | `docs/REPO_TRUTH_MATRIX.md`, `docs/REPO_FREEZE_GAP_MATRIX.md`                                                |
| Produktstatus KI/UX          | `PRODUCT_STATUS.md`, `ai-architecture.md`, `release-readiness.md`                                            |
| Integrations- und Fehlerbild | `API_INTEGRATION_STATUS.md`                                                                                  |
| Compose-Topologie            | `docker-compose.yml`, `docker-compose.local-publish.yml`, `docs/compose_runtime.md`                          |
| Service-Katalog              | `infra/service-manifest.yaml`                                                                                |
| Gateway-App                  | `services/api-gateway/src/api_gateway/app.py` (üblich), Routen unter `services/api-gateway/src/api_gateway/` |
| LLM-Dienst                   | `services/llm-orchestrator/src/llm_orchestrator/app.py`, `api/routes.py`                                     |
| Signal-Kern                  | `services/signal-engine/`                                                                                    |
| Live-Ausführung              | `services/live-broker/`                                                                                      |
| Dashboard-App                | `apps/dashboard/src/app/`                                                                                    |
| Shared Python                | `shared/python/src/shared_py/`                                                                               |
| ENV-Profile                  | `docs/env_profiles.md`, `.env*.example` im Root                                                              |
| Tests                        | `tests/`, `shared/python/tests/`, `apps/dashboard` (Jest), `e2e/`                                            |
| CI                           | `.github/workflows/ci.yml`                                                                                   |
| Root-Skripte                 | `package.json` (`pnpm dev:up`, `smoke`, `release:gate`, …), `scripts/*.ps1`, `scripts/*.sh`                  |

---

## 14. Übergabe an ChatGPT

**Arbeitsauftrag für das Folgemodell:**

1. Behandle **`docs/REPO_TRUTH_MATRIX.md`** und **`PRODUCT_STATUS.md`** als primäre **Ist**-Quellen für Lücken und Reife; **`docs/adr/ADR-0001-bitget-market-universe-platform.md`** als **Soll**-Architektur.
2. Prüfe bei konkreten Feature-Fragen immer **Code + Compose** (z. B. `docker-compose.yml`, `services/*/src`) — nicht nur Markdown.
3. Unterscheide strikt: **deterministischer Trading-Kern** vs. **LLM-Hilfspfad**; keine Annahme, dass jeder Orchestrator-Endpunkt im Dashboard sichtbar ist.
4. Für lokale Reproduktion: `README.md` → `docs/LOCAL_START_MINIMUM.md` → `pnpm dev:up` / `scripts/bootstrap_stack.ps1` je nach Umgebung.
5. Sicherheit: keine Secrets ins Repo; Keys nur via ENV/Secret Manager (**verifiziert:** `README.md` Security Rules).

---

## 15. Anhang mit belegenden Dateipfaden

### Kern-Dokumentation

- `README.md`
- `docs/adr/ADR-0001-bitget-market-universe-platform.md`
- `docs/REPO_TRUTH_MATRIX.md`
- `docs/REPO_FREEZE_GAP_MATRIX.md` (in Matrix referenziert)
- `PRODUCT_STATUS.md`
- `ai-architecture.md`
- `release-readiness.md`
- `API_INTEGRATION_STATUS.md`
- `docs/PRODUCT_PLANS_AND_USAGE.md`
- `docs/SYSTEM_AUDIT_MASTER.md` (laut README Verweis)

### Laufzeit & Pakete

- `docker-compose.yml`
- `docker-compose.local-publish.yml`
- `infra/service-manifest.yaml`
- `package.json` (Root)
- `apps/dashboard/package.json`
- `services/*/pyproject.toml` (13 Services)
- `turbo.json`

### KI (Implementierung)

- `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`
- `services/llm-orchestrator/src/llm_orchestrator/app.py`
- `services/news-engine/src/news_engine/scoring/llm_enricher.py`
- `tests/unit/api_gateway/test_routes_llm_operator.py` (Stichwort Gateway-LLM)

### Dashboard (Routen-Stichprobe)

- `apps/dashboard/src/app/(operator)/console/health/page.tsx`
- `apps/dashboard/src/app/(operator)/console/signals/page.tsx`
- `apps/dashboard/src/app/(operator)/console/signals/[id]/page.tsx`
- `apps/dashboard/src/app/(operator)/console/ops/page.tsx`

### Shared / Verträge

- `shared/python/src/shared_py/`
- `shared/contracts/`
- `config/settings.py` (zentral referenziert in Matrix)

### Datenbank

- `infra/migrations/postgres/*.sql` (**85** Dateien, Stand Zählung 2026-04-04)

### Qualitätssicherung

- `.github/workflows/ci.yml`
- `tools/production_selfcheck.py`
- `scripts/release_gate.py`
- `e2e/playwright.config.ts`

---

_Ende der Übergabedatei._
