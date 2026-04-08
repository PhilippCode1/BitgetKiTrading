# AUDIT_REPORT — Vorbericht (Totalaudit Prompt A)

**Datum (Report):** 2026-04-07 · **Runde:** 3  
**Branch:** `master`  
**Commit-Hash (HEAD):** `85404cd6488c5cfce6a37636d7c7fb34e1dac96b`  
**Umfeld:** Windows, PowerShell; **dynamischer Stack und `pnpm e2e` in diesem Audit-Lauf nicht ausgefuehrt** (Evidence: `AUDIT_EVIDENCE/RUN_2026-04-07_PROMPT_A_ROUND3.md`).

**Delta seit Runde 2:** Sprint 2 (Prompt B) lieferte Marktuniversum-**Daten-Lineage-Panel**, **Kernsymbole BTCUSDT/ETHUSDT**, **serverseitige Pagination** fuer Universe-Symbole und Instrument-Registry, plus Unit-Tests und E2E-Erweiterung in `release-gate.spec.ts` (Commit `a511b8c`).

---

## Executive Summary

Das Repository `bitget-btc-ai` bleibt eine **End-to-End-Zielarchitektur** (Worker-Kette → API-Gateway → Next.js-Dashboard → Observability → LLM-Orchestrator mit Schemas/Eval-Tooling).

**Streng bewertet weiterhin FAIL oder Luecke:**

1. **Phase 3 (Laufzeit):** Kein `compose up`, keine aggregierten Logs/Health-Auszuege in **diesem** Lauf.  
2. **UI-Totalabdeckung:** Playwright deckt Kernpfade, Sidebar, Marktuniversum-Lineage; **kein** vollstaendiger In-Content-Link-/Button-Crawl, keine dynamischen `[id]`-Stichproben automatisierbar ohne Daten.  
3. **KI 10/11:** Ohne frische Eval-Laeufe und Schwellen pro Use-Case = **FAIL** gegen Zielbild.  
4. **Pro-Symbol-Produkt-Vollstaendigkeit** (Chart + Orderbook + Signals + News + Performance fuer **beliebiges** Symbol): **nicht** garantiert / nicht belegt.  
5. **Terminal / Signale:** Dieselbe **explizite** Datenpfad-Darstellung wie auf Marktuniversum — **noch nicht** umgesetzt (Backlog Sprint 2b).

---

## PHASE 1 — Baseline & Reproduzierbarkeit

### Git (Prompt A Runde 3)

| Check | Ergebnis |
|--------|----------|
| Branch | `master` |
| HEAD | `85404cd6488c5cfce6a37636d7c7fb34e1dac96b` |
| Status | clean |
| Diff | kein lokaler Diff zum HEAD |

### package.json (Root) — Scripts (Kategorien)

- **Monorepo:** `dev`, `build`, `lint`, `test`, `check-types`, `format`, `format:check`  
- **Stack (Windows):** `dev:up`, `dev:down`, `dev:status`, `dev:logs`, `rc:health`, `smoke`, `stack:check`, `local:doctor`  
- **Konfiguration:** `config:validate*`, `config:validate:operator/shadow/production`  
- **E2E:** `e2e`, `e2e:ui`, `e2e:debug`, `e2e:install`  
- **KI:** `llm:eval`, `llm:eval:report`  
- **Qualitaet:** `quality:static`, `release:gate`, `release:gate:full`  
*(Vollstaendige Liste: `package.json`.)*

### Docker Compose

- **Dateien:** `docker-compose.yml`, `docker-compose.local-publish.yml` (CI)  
- **Validierung Runde 3:** `docker compose -f docker-compose.yml config --quiet` → Exit 0  
- **Services (Kern):** postgres, redis, migrate, market-stream, feature-/structure-/drawing-/signal-engine, news-engine, llm-orchestrator, paper-broker, learning-engine, live-broker, api-gateway, alert-engine, monitor-engine, optional dashboard, prometheus, grafana  
- **Host-Ports (typisch):** Gateway **8000**, Dashboard **3000**, Prometheus **9090**, Grafana **3001** → 3000  
- **ENV:** `BITGET_*`, Universe/Watchlist/Scopes, DB/Redis, Gateway-JWT

### ENV-Profile

- Vorlagen: `.env.*.example`  
- **Validator Runde 3:** temporaere `.env.local.example` mit CI-Platzhalter-Ersatz → **OK** (`local`)

### Reproduktions-Setup

1. `pnpm install --frozen-lockfile`  
2. `.env.local`; `pnpm config:validate`  
3. `docker compose up -d` oder `pnpm dev:up`  
4. `pnpm rc:health` / `pnpm local:doctor`  
5. Dashboard lokal oder Compose-Profil  
6. `pnpm e2e` mit `E2E_BASE_URL`  
7. Optional `pnpm llm:eval`

---

## PHASE 2 — Architektur & Verdrahtung (statisch)

### Systemuebersicht

| Komponente | Rolle |
|------------|--------|
| `market-stream` | Bitget/WS → Redis / Downstream |
| `feature-engine` / `structure-engine` / `drawing-engine` | Pipeline bis Chart-Logik |
| `signal-engine` | Signale |
| `news-engine` | News |
| `live-broker` / `paper-broker` | Ausfuehrung |
| `learning-engine` | Lernpfad |
| `api-gateway` | Aggregation, `/v1/system/health`, `/v1/market-universe/status`, … |
| `llm-orchestrator` | Strukturierte LLM-Responses |
| `apps/dashboard` | Next.js + BFF `/api/dashboard/*` |

### Datenfluss (Zielbild)

`Market-Stream` → `Feature` → `Structure` → `Drawing` → `Signal` → Broker → `API-Gateway` → `Dashboard`.

### Events / Queues

- Redis + Postgres; Details `ai-architecture.md` / Service-READMEs.  
- **FAIL** fuer SRE-10/10: Drops/Backpressure ohne Messung.

### Ungenutzte / halbe Services

- `alert-engine`, `monitor-engine` — Abgleich mit tatsaechlicher Dashboard-Nutzung empfohlen.

---

## PHASE 3 — Laufzeit-Check (dynamisch)

**Status:** Nicht ausgefuehrt (siehe `RUN_2026-04-07_PROMPT_A_ROUND3.md`).

**Naechster DoD:** `docker compose ps`, `healthcheck.sh` / `rc:health`, Logs je Kernservice, Prometheus Targets, Anhang in neuer `RUN_*.md`.

---

## PHASE 4 — UI/UX Totalpruefung

### Routen

- `AUDIT_EVIDENCE/ROUTE_INVENTORY_DASHBOARD.md`  
- `AUDIT_EVIDENCE/API_ROUTES_DASHBOARD.md`

### E2E (Playwright)

| Spec | Zweck |
|------|--------|
| `release-gate.spec.ts` | edge-status, Operator-Explain, Kern-Konsole, **Marktuniversum + `data-testid=market-universe-lineage`**, Terminal |
| `trust-surfaces.spec.ts` | Trust-Flaechen |
| `responsive-shell.spec.ts` | Shell |
| `broken-interactions.spec.ts` | Sidebar-Links, `/`, `/welcome` |

### Artefakte

- `BROKEN_LINKS.md`, `BROKEN_BUTTONS.md`, `INCOMPLETE_PAGES.md` — fortgefuehrt; **kein** vollautomatischer Gesamt-Crawl.

**FAIL** gegen „jeder Button/Link“: In-Page-Aktionen, Formulare, dynamische IDs, Admin-Gates ohne Nav.

---

## PHASE 5 — Marktuniversum

- **Konfiguration:** ENV/Compose — datengetrieben.  
- **UI (neu):** `MarketUniverseDataLineagePanel`: Ausfuehrungsmodus, LIVE/SHADOW/PAPER-Pills, letzte Kerze/Signal (Plattform), **market-stream** + **live-broker** Health, WS-Telemetrie-Kurztext, **Broker-Reconcile**, Tabelle **BTCUSDT/ETHUSDT** mit Registry- und Chart-Link; **Pagination** `universePage` (32), `registryPage` (40).  
- **Families / Spot-Margin-Futures:** weiterhin im Gateway/Produktspec zu verifizieren — **RISK**.  
- **Backpressure / Zeitreihen-Volumen:** ohne Lasttest **unbelegt** (P1-4).  
- **Beliebiges Symbol:** Chart ueber URL/Symbolwahl moeglich; Orderbook/News/Signals nicht fuer jedes Symbol als Paket garantiert — **FAIL** bis spezifiziert und getestet.

---

## PHASE 6 — KI Totalpruefung

- **Inventar:** Orchestrator, `shared/contracts/schemas`, `shared/prompts`, Dashboard-BFF LLM-Routen, `tools/run_llm_eval.py`, `tests/llm_eval`, CI `validate_eval_baseline.py`.  
- **Qualitaet:** Guardrails ja; **10/10** nein ohne Evidenz-Laeufe.  
- Details: `AUDIT_SCORECARD.md` (KI-Abschnitt), `AUDIT_BACKLOG.md` P1-5.

---

## PHASE 7 — Security / Compliance / Fehlermeldungen

- Secrets: Validator + Doku; kein Scan in Runde 3.  
- Fehler-UX: Gateway-Bootstrap, Diagnose, Self-Healing, Situation-Explain — stark.  
- **Silent error classes:** `res.json().catch(() => ({}))` an wenigen Stellen — pruefen ob immer UI-Folge.  
- Error Boundaries: nicht flaechendeckend verifiziert.

---

## PHASE 8 — Deliverables

| Artefakt | Pfad |
|----------|------|
| Scorecard | `AUDIT_SCORECARD.md` |
| Backlog | `AUDIT_BACKLOG.md` |
| Sprints | `SPRINT_PLAN.md` |
| Evidence | `AUDIT_EVIDENCE/*` |

**Plan Prompt B:** `SPRINT_PLAN.md` + Backlog — naechster sinnvoller Schritt: **Terminal/Signals** Datenpfad wie MU, **P0-3** Stack-Smoke, **Sprint 3** KI-Eval-Gates.

---

## Top-Findings (konsolidiert, Runde 3)

1. Kein Stack-/Log-Nachweis in Runde 3.  
2. E2E-Gesamtlauf lokal ausstehend.  
3. KI weiter ohne frische Eval-Evidenz.  
4. Terminal/Signals: Transparenz-Luecke vs. Marktuniversum.  
5. Marktuniversum: UX verbessert; Lastprofil 500+ offen.  
6. Pro-Symbol-Vollstaendigkeit (Chart+Orderbook+News+Signals+Performance) unbelegt.  
7. Pipeline-Drops: ungemessen.  
8. Grafana/Alerts/Runbooks: unverifiziert.  
9. Zwei Dashboard-Betriebsmodi dokumentieren.  
10. Forensic/dynamische Routen: Stichproben.  
11. i18n-Reste Matrix.  
12. Button-/Form-Matrix (P1-2) offen.  
13. Remote-CI: hier nicht erneut ausgefuehrt.  
14. Body-parse-catches: Review-Liste (4 Stellen).  
15. Admin-Nav: nur bei Gateway-Auth sichtbar — E2E kontextabhaengig.

---

*Ende Vorbericht. Evidence-Runde:* `RUN_2026-04-07_PROMPT_A_ROUND3.md`
