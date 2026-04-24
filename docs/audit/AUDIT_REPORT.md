# AUDIT_REPORT — Vorbericht (Totalaudit Prompt A)

> **P83 (2026-04-24):** Dieser Bericht ist ein **Stichtag-Snapshot** (Runde 5, Commit unten). **Aktueller** technischer Stand, Gates **Phase 1–18** und P0-Abnahme: [SYSTEM_AUDIT_MASTER.md](../SYSTEM_AUDIT_MASTER.md), [LaunchChecklist.md](../LaunchChecklist.md), [REPO_FREEZE_GAP_MATRIX.md](../REPO_FREEZE_GAP_MATRIX.md). Findings in Abschnitt „Executive Summary“ und **FAIL**-Markierungen beschreiben den Befund vom **2026-04-08**, nicht notwendig den heutigen Zustand — Gegenprüfung nur über kanonische Docs und CI.

**Datum (Report):** 2026-04-08 · **Aktive Runde:** **5**  
**Branch:** `master`  
**Commit-Hash (HEAD):** `e871b871b4a8cd803edcec50ca763e50cad7078c`  
**Arbeitsbaum:** **clean**  
**Evidence (Runde 5):** `AUDIT_EVIDENCE/RUN_2026-04-08_PROMPT_A_ROUND5.md`  
**Weitere Evidence:** `RUN_2026-04-07_PROMPT_A_ROUND4.md`, `RUN_PROMPT_B_SPRINT1_2026-04-08.md`, `RUN_SPRINT2b_TERMINAL_SIGNALS_LINEAGE.md`

**Runde 5 — verifiziert:** `docker compose config` Exit 0; `docker compose ps` Container **healthy**; `pnpm check-types` grün; `pytest tests/llm_eval` **23 passed**.  
**Runde 5 — hartes Finding:** `pnpm rc:health` in diesem Lauf **nicht grün**: Gateway-`/ready` mit **`redis: Timeout reading from socket`**, dazu Timeouts und **degradierte Worker** laut `system-health` — siehe `RUN_2026-04-08_PROMPT_A_ROUND5.md`.

**Delta (kumulativ bis HEAD):** Marktuniversum-Lineage + Pagination; **Terminal/Signale** mit `PlatformExecutionStreamsGrid` (committed in `42fe623`); Hydration-Fix `LiveDataSituationBar`; erweiterte **broken-interactions** E2E.

---

## Executive Summary

Das Repository `bitget-btc-ai` bleibt eine **End-to-End-Zielarchitektur** (Worker-Kette → API-Gateway → Next.js-Dashboard → Observability → LLM-Orchestrator mit Schemas/Eval-Tooling).

**Streng bewertet weiterhin FAIL oder Luecke:**

1. **Phase 3 (Laufzeit):** **Runde 5:** `rc:health` zeigt **Redis-Timeouts** und **Worker-Degradation** — **FAIL** gegen „stabil reproduzierbar grün“.  
2. **UI-Totalabdeckung:** Playwright deckt Sidebar + kritische Pfade + sichere Klicks; **kein** vollständiger In-Content-Crawl, keine flächendeckenden `[id]`-Stichproben.  
3. **KI 10/11:** `tests/llm_eval` grün — **FAIL** gegen Nutzer-Qualität 10/10 ohne Feldmetriken, SLO, CI-Artefakt pro Release.  
4. **Pro-Symbol-Produkt-Vollstaendigkeit** (Chart + Orderbook + Signals + News + Performance für **beliebiges** Symbol): **nicht** garantiert / nicht belegt.  
5. **SRE/MTTR:** Schwankende Edge-Gesundheit trotz „container healthy“ — Diagnosepfad für Operateure muss **Redis + Gateway** klar machen (Runbook, UI).

---

## PHASE 1 — Baseline & Reproduzierbarkeit

### Git (Prompt A Runde 5)

| Check | Ergebnis |
|--------|----------|
| Branch | `master` |
| HEAD | `e871b871b4a8cd803edcec50ca763e50cad7078c` |
| Status | **clean** |
| Parent Feature-Commit | `42fe623` — Hydration, E2E, `PlatformExecutionStreamsGrid`, Terminal/Signals |

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

**Status Runde 5:** **Teilweise** ausgeführt — `docker compose ps` (healthy), **`pnpm rc:health` in diesem Lauf degradiert/FAIL** (Redis-Timeout im Gateway-`/ready`, Worker nicht ok, Dashboard-API-Health teils timeout). Evidence: `RUN_2026-04-08_PROMPT_A_ROUND5.md`.

**Naechster DoD:** Redis-Stabilität root-causen; Logs `api-gateway`, `redis`; wiederholbarer grüner `rc:health`-Lauf dokumentieren; optional `pnpm dev:status`.

---

## PHASE 4 — UI/UX Totalpruefung

### Routen

- `AUDIT_EVIDENCE/ROUTE_INVENTORY_DASHBOARD.md`  
- `AUDIT_EVIDENCE/API_ROUTES_DASHBOARD.md`

### E2E (Playwright)

| Spec | Zweck |
|------|--------|
| `release-gate.spec.ts` | edge-status, Operator-Explain, Kern-Konsole, **`market-universe-lineage`**, Terminal + **`platform-execution-lineage-terminal`**, Signale + **`platform-execution-lineage-signals`** |
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
- **Backpressure / Zeitreihen-Volumen (P1-4 / Prompt 80):** Werkzeuge und Leitplanken sind im Repo, **Voll-DoD (30-Min-Referenzlauf) ist lokal/ohne laufende Pipeline nicht ersetzbar** — siehe **P80** unten.  
- **Beliebiges Symbol:** Chart ueber URL/Symbolwahl moeglich; Orderbook/News/Signals nicht fuer jedes Symbol als Paket garantiert — **FAIL** bis spezifiziert und getestet.

---

## P80 — Scalability Sign-off (High-Frequency Marktuniversum)

**Ziel (DoD):** 500 parallele Symbole × 10 Ticks/s = **5.000 Events/s** Ziel-Last; **Drop-Rate** (Summe `pipeline_event_drop_total` über `market-stream` + `feature-engine` `/metrics`, Delta zum Laufbeginn) **unter 0,01 %**; **kein `MemoryError`** (Feeder/Beobachterprozess); **CPU-Last** lokal (psutil) ohne pathologische Einzelspitze (Werkzeug prüft Stichproben-`cpu_percent`‑Streuung); **Gleichmässige Ziel-Rate** (≥ 85 % des theoretischen Soll-EPS).

| Baustein | Beschreibung |
|----------|----------------|
| `tools/hf_universe_stress.py` | `HighFrequencyMockFeeder`: Round-Robin-`market_tick` auf `events:market_tick` (Redis), **dedupe** aus, Ziel-Rate `symbols × ticks_per_sec`. |
| `FEATURE_TSFM_TICK_CONCURRENCY` | `feature-engine`: `asyncio.Semaphore` in der TSFM-Pipeline, begrenzt offene `asyncio`-Task‑Parallelität (Default **1**). |
| Metriken | Vor/nach: Summe aller `pipeline_event_drop_total{...}`-Zeilen aus gegebenen `/metrics`‑URLs. |
| Sign-off-JSON | `--out-json` (z. B. `docs/audit/hf_stress_signoff.json`), Feld `signoff_ok` = Gate über Drop-Rate, Memory, CPU-Fairness, EPS-Ratio. |

**Referenzbefehl (Voll-DoD, 30 Min):** voller Stack, **Redis**, `market-stream` (typ. :8010), `feature-engine` (typ. :8020) erreichbar. Das Skript setzt `sys.path` inkl. Repo-Root; Aufruf aus dem Repository-Verzeichnis:

```text
python tools/hf_universe_stress.py --duration-sec 1800 --symbols 500 --ticks-per-symbol 10 ^
  --market-stream-metrics-url http://127.0.0.1:8010/metrics ^
  --feature-engine-metrics-url http://127.0.0.1:8020/metrics ^
  --out-json docs/audit/hf_stress_signoff.json
```

**Einstufung in diesem Report:** *Scalability Sign-off* = **Durchführung +** `signoff_ok: true` **im** `hf_stress_signoff.json` (nach produktionsnahem 30-Min-Lauf) **bzw.** gleichwertiges Artefakt mit identischer Methodik. Ohne solches Artefakt bleibt P1-4 fachlich **dokumentierbar, aber** die Runtime-Nachweis-**Evidenz** aus Runde 5/6 **hängt** am tatsächlichen Durchlauf.

**Kurzlauf (CI/Entwicklung):** Standard-Argumente lassen `market-stream-metrics-url` leer; dann werden **keine** Drops bewertet (`pass_drop_rate` = ok), nur Publish- und EPS-Checks. Mit Stack: dieselben URLs wie im 30-Min-Beispiel setzen.

```text
python tools/hf_universe_stress.py --duration-sec 10
```

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

**Plan Prompt B:** `SPRINT_PLAN.md` + Backlog — naechster sinnvoller Schritt: **Redis/Gateway-Stabilität** (P0), **P1-6** Ribbon vs. Bar, **P1-4** Universe-Last, **Sprint 3** KI-Gates + CI-Artefakte.

---

## Top-Findings (Runde 5 — ergänzend)

1. **`rc:health` FAIL / instabil** — Redis-Socket-Timeout im Gateway; Worker laut system-health nicht ok.  
2. **Container „healthy“ ≠ Edge grün** — Betrieb muss beides differenzieren.  
3. **`pnpm e2e`** in Runde 5 nicht erneut belegt (abhängig von Gateway/Redis).  
4. **`config:validate`** gegen echte `.env.local` ausstehend.  
5. **KI:** pytest `llm_eval` grün, aber **kein** Nachweis menschenzentrierter Qualität / Fehlerquoten-SLO.  
6. **In-Page-Links/Buttons** jenseits Sidebar: weiter **FAIL** vs. Totalprüfung.  
7. **P1-4** Lastprofil Marktuniversum: **Härtung +** `tools/hf_universe_stress.py` (P80); **Evidenz** = 30-Min-`signoff_ok` bzw. `hf_stress_signoff.json` — **ohne Artefakt** weiterhin inhaltlich *unvollständig* vs. DoD.  
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

*Ende Vorbericht. Evidence Runde 5:* `RUN_2026-04-08_PROMPT_A_ROUND5.md` · *Runde 4:* `RUN_2026-04-07_PROMPT_A_ROUND4.md` · *Runde 3:* `RUN_2026-04-07_PROMPT_A_ROUND3.md`
