# AUDIT_REPORT — Vorbericht (Totalaudit Prompt A)

**Datum (Report):** 2026-04-07 · **Aktive Runde:** **4**  
**Branch:** `master`  
**Commit-Hash (HEAD):** `cce2525ac2ef9dadc380e5192b36938d46792a9c`  
**Arbeitsbaum:** **nicht clean** (Sprint-2b-Änderungen: `PlatformExecutionStreamsGrid`, Terminal/Signals, E2E, i18n — vor Commit).  
**Evidence (Runde 4):** `AUDIT_EVIDENCE/RUN_2026-04-07_PROMPT_A_ROUND4.md`  
**Vorherige Evidence:** `RUN_2026-04-07_PROMPT_A_ROUND3.md` (Runde 3, HEAD `85404cd…`).

**Runde 4 — neu verifiziert:** `docker compose config` Exit 0; `pnpm check-types` grün; `pytest tests/llm_eval` **23 passed** (lokal).  
**Prompt B Sprint 1 (2026-04-08):** Hydration **React #418** in `LiveDataSituationBar` behoben (`Date.now()` nur nach mount); E2E broken-interactions erweitert; `pnpm rc:health` dokumentiert grün — siehe `RUN_PROMPT_B_SPRINT1_2026-04-08.md`.

**Delta (kumulativ):** Marktuniversum-**Lineage**, **Pagination**; im Arbeitsbaum zusätzlich **gemeinsame Health-Lineage** für Terminal/Signale (`PlatformExecutionStreamsGrid`) + Release-Gate-`testid`s.

---

## Executive Summary

Das Repository `bitget-btc-ai` bleibt eine **End-to-End-Zielarchitektur** (Worker-Kette → API-Gateway → Next.js-Dashboard → Observability → LLM-Orchestrator mit Schemas/Eval-Tooling).

**Streng bewertet weiterhin FAIL oder Luecke:**

1. **Phase 3 (Laufzeit):** Kein `compose up`, keine aggregierten Logs/Health-Auszuege in **Runde 4**.  
2. **UI-Totalabdeckung:** Playwright deckt Sidebar, Release-Gate (inkl. Marktuniversum-Lineage; im WT: Terminal/Signals-Lineage-`testid`s); **kein** vollstaendiger In-Content-Link-/Button-Crawl, keine dynamischen `[id]`-Stichproben flächendeckend.  
3. **KI 10/11:** Eval-**Suite** läuft lokal grün (23 Tests) — **trotzdem FAIL** gegen „überall messbar 10/10“: kein Nutzer-Erlebnis-/Qualitäts-Score pro Use-Case, kein CI-Artefakt in diesem Lauf, keine harten Gates in PR dokumentiert.  
4. **Pro-Symbol-Produkt-Vollstaendigkeit** (Chart + Orderbook + Signals + News + Performance fuer **beliebiges** Symbol): **nicht** garantiert / nicht belegt.  
5. **Terminal / Signale vs. Marktuniversum:** Lücke **im committed HEAD** noch offen; **im Arbeitsbaum** adressiert (Prompt B Sprint 2b) — bis Merge **FAIL** für „released“ Produkt.

---

## PHASE 1 — Baseline & Reproduzierbarkeit

### Git (Prompt A Runde 4)

| Check | Ergebnis |
|--------|----------|
| Branch | `master` |
| HEAD | `cce2525ac2ef9dadc380e5192b36938d46792a9c` |
| Status | **dirty** (siehe `git status`; Sprint 2b / Audit-Dateien) |
| Diff | lokal vs. HEAD: mehrere `apps/dashboard/*`, `e2e/*`, `docs/audit/*` |

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
- **Runde 4:** kein vollständiger `config:validate`-Lauf gegen produktive `.env.local` in diesem Audit (Gap).

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

**Status Runde 4:** Weiterhin **nicht** ausgefuehrt (kein `compose up`, keine `rc:health`-Ausgabe in Evidence).

**Naechster DoD:** `docker compose ps`, `pnpm rc:health` / `pnpm dev:status`, Logs je Kernservice, Prometheus Targets, Anhang in `RUN_*_STACK.md`.

---

## PHASE 4 — UI/UX Totalpruefung

### Routen

- `AUDIT_EVIDENCE/ROUTE_INVENTORY_DASHBOARD.md`  
- `AUDIT_EVIDENCE/API_ROUTES_DASHBOARD.md`

### E2E (Playwright)

| Spec | Zweck |
|------|--------|
| `release-gate.spec.ts` | edge-status, Operator-Explain, Kern-Konsole, **Marktuniversum + `market-universe-lineage`**, Terminal (+ im WT: **`platform-execution-lineage-terminal`**, **`platform-execution-lineage-signals`**) |
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
- **Qualitaet Runde 4:** `pytest tests/llm_eval` → **23 passed** (Fake/Guardrail/Regression — kein Ersatz für Endnutzer-Qualität 10/10).  
- **10/11 Ziel:** weiter **FAIL** ohne produktnahe Metriken, SLO für LLM-Fehlerquote, und PR-Gate mit Artefakt pro Release.  
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

**Plan Prompt B:** `SPRINT_PLAN.md` + Backlog — naechster sinnvoller Schritt: **Commit** Sprint 2b + **P0-3** Stack-Smoke + **P1-6** Ribbon vs. Bar + **Sprint 3** KI-Eval-Gates in CI mit Artefakten.

---

## Top-Findings (Runde 4 — ergänzend)

1. **Arbeitsbaum dirty** — released Stand ≠ HEAD bis Merge/Commit Sprint 2b.  
2. **Stack/Health** weiter ohne Messung in Runde 4.  
3. **`pnpm e2e`** nicht gelaufen — Release-Gate-Änderungen im WT unverifiziert gegen Live-URL.  
4. **`config:validate`** gegen echte `.env.local` ausstehend.  
5. **KI:** pytest `llm_eval` grün, aber **kein** Nachweis menschenzentrierter Qualität / Fehlerquoten-SLO.  
6. **In-Page-Links/Buttons** jenseits Sidebar: weiter **FAIL** vs. Totalprüfung.  
7. **P1-4** Lastprofil Marktuniversum unbelegt.  
8. **P1-6** Ribbon vs. `LiveDataSituationBar` — Konflikt-UX offen.

## Top-Findings (konsolidiert, Runde 3 — historisch)

1. Kein Stack-/Log-Nachweis in Runde 3.  
2. E2E-Gesamtlauf lokal ausstehend.  
3. KI weiter ohne frische Eval-Evidenz (Runde 3).  
4. Terminal/Signals: Transparenz-Luecke vs. Marktuniversum (Runde 3; siehe Runde 4 WT).  
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

*Ende Vorbericht. Evidence Runde 4:* `RUN_2026-04-07_PROMPT_A_ROUND4.md` · *Runde 3:* `RUN_2026-04-07_PROMPT_A_ROUND3.md`
