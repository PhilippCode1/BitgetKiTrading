# AUDIT_REPORT — Vorbericht (Totalaudit Prompt A)

**Datum (Report):** 2026-04-07  
**Branch:** `master`  
**Commit-Hash (HEAD):** `f09221a47f834388232358ab66d5f8f616d95995`  
**Umfeld:** Windows, PowerShell; **dynamischer Stack-Lauf und `pnpm e2e` in diesem Audit-Lauf nicht ausgefuehrt** (siehe Evidence `AUDIT_EVIDENCE/RUN_2026-04-07.md`).

**Historie:** Erstlauf 2026-04-08 dokumentiert in `RUN_2026-04-08.md` (damals ohne Commit); Sprint-1-Import in `RUN_SPRINT1_2026-04-08.md` (Root-Commit `54f3917…`). Dieser Report **ersetzt** veraltete Aussagen („kein Git-Commit“) und konsolidiert den aktuellen Stand.

---

## Executive Summary

Das Repository `bitget-btc-ai` implementiert eine **End-to-End-Zielarchitektur**: Marktstream ueber Worker-Services bis **API-Gateway** und **Next.js-Dashboard** (BFF + Konsole), ergaenzt um **Prometheus/Grafana**, **LLM-Orchestrator** mit JSON-Schemas und **Eval-/Contract-Tooling** in CI (siehe `.github/workflows/ci.yml`).

**Streng bewertet bleiben Luecken:**

1. **Laufzeitbeweis** auf diesem Host: kein `compose up`, keine aggregierten Service-Logs, keine JUnit-Auswertung von E2E hier.  
2. **UI-Totalabdeckung:** Playwright deckt Kernpfade + **Sidebar-Link-Traversal** (`broken-interactions.spec.ts`); **kein** vollstaendiger Crawl aller In-Content-Links, Form-Buttons und dynamischen `[id]`-Routen ohne Stichproben.  
3. **KI 10/11:** Werkzeuge und CI-Baseline (`validate_eval_baseline.py`) vorhanden; **messbare Qualitaet pro Use-Case** ohne regelmaessige Eval-Artefakte + Schwellen = **FAIL** gegen Zielbild.  
4. **Marktuniversum:** Konfiguration ueber ENV skalierbar; **UI/Performance bei sehr grossen N** und **Vollstaendigkeit Chart/Orderbook/News pro Symbol** nicht voll belegt.

---

## PHASE 1 — Baseline & Reproduzierbarkeit

### Git (2026-04-07)

| Check | Ergebnis |
|--------|----------|
| Branch | `master` |
| HEAD | `f09221a47f834388232358ab66d5f8f616d95995` |
| Status | clean |
| Diff | kein lokaler Diff zum HEAD |

### package.json (Root) — Scripts (Kategorien)

- **Monorepo:** `dev`, `build`, `lint`, `test`, `check-types`, `format`, `format:check`  
- **Stack (Windows):** `dev:up`, `dev:down`, `dev:status`, `dev:logs`, `rc:health`, `smoke`, `stack:check`, `local:doctor`  
- **Konfiguration:** `config:validate`, `config:validate:operator`, `config:validate:shadow`, `config:validate:production`  
- **E2E:** `e2e`, `e2e:ui`, `e2e:debug`, `e2e:install`  
- **KI:** `llm:eval`, `llm:eval:report`  
- **Qualitaet:** `quality:static`, `release:gate`, `release:gate:full`  
*(Vollstaendige Liste: Datei `package.json`.)*

### Docker Compose

- **Dateien:** `docker-compose.yml` (+ lokal `docker-compose.local-publish.yml` in CI)  
- **Validierung dieses Laufs:** `docker compose -f docker-compose.yml config --quiet` → Exit 0  
- **Services (Kern):** `postgres`, `redis`, `migrate`, `market-stream`, `feature-engine`, `structure-engine`, `drawing-engine`, `signal-engine`, `news-engine`, `llm-orchestrator`, `paper-broker`, `learning-engine`, `live-broker`, `api-gateway`, `alert-engine`, `monitor-engine`, optional `dashboard` (Profil), `prometheus`, `grafana`  
- **Host-Ports (typisch aus Compose):** API-Gateway **8000** → Container 8000; Dashboard-Profil **3000** → 3000; Prometheus **9090**; Grafana **3001** → 3000; Postgres/Redis oft nur intern (siehe `ports:`-Bloecke im YAML).  
- **ENV:** `BITGET_*`, Universe/Watchlist/Scopes, DB/Redis-URLs, Gateway-JWT — siehe `environment` und `env_file` im Compose.

### ENV-Profile

- Vorlagen: `.env.example`, `.env.local.example`, `.env.production.example`, `.env.shadow.example`, `.env.test.example`  
- **Validator:** `tools/validate_env_profile.py` — in diesem Lauf gegen temporaere Kopie von `.env.local.example` mit `<SET_ME>`-Ersatz (**OK**, Profil `local`), analog CI-Schritt.

### Reproduktions-Setup

1. `pnpm install --frozen-lockfile`  
2. `.env.local` aus Example; `pnpm config:validate`  
3. `docker compose up -d` (oder `pnpm dev:up` unter Windows)  
4. `pnpm rc:health` / `pnpm local:doctor`  
5. Dashboard: `pnpm --filter @bitget-btc-ai/dashboard dev` oder Compose-Profil `with-dashboard`  
6. `pnpm e2e` mit `E2E_BASE_URL` (z. B. `http://127.0.0.1:3000`)  
7. Optional: `pnpm llm:eval`

---

## PHASE 2 — Architektur & Verdrahtung (statisch)

### Systemuebersicht

| Komponente | Rolle |
|------------|--------|
| `market-stream` | Bitget/WebSocket → Redis / Downstream |
| `feature-engine` | Feature-Vektoren |
| `structure-engine` | Marktstruktur |
| `drawing-engine` | Chart-/Linienlogik |
| `signal-engine` | Signale |
| `news-engine` | News-Feed |
| `live-broker` / `paper-broker` | Ausfuehrung bzw. Paper |
| `learning-engine` | Lern-/Feedback-Pfad |
| `api-gateway` | HTTP-Aggregation, Auth, Routing |
| `llm-orchestrator` | Strukturierte LLM-Calls |
| `apps/dashboard` | Next.js UI + BFF unter `/api/dashboard/*` |

### Datenfluss (Zielbild)

`Market-Stream` → `Feature` → `Structure` → `Drawing` → `Signal` → Broker → `API-Gateway` → `Dashboard`.

### Events / Queues / Streams

- **Redis** und **Postgres** als zentrale Infrastruktur; Details pro Service in `services/*/README` bzw. `ai-architecture.md`.  
- **Risiko:** Ohne Laufzeit-Metriken keine belastbare Aussage zu **Drops**, **Lag** oder **Backpressure** — **FAIL** fuer SRE-Ziel 10/10 bis gemessen.

### Ungenutzte / halbe Services

- Zusaetzliche Engines (`alert-engine`, `monitor-engine`) erfordern Abgleich mit tatsaechlichen Produktflows im Dashboard — stichprobenartig in Prompt B verifizieren.

---

## PHASE 3 — Laufzeit-Check (dynamisch)

**Status:** In `RUN_2026-04-07.md` **nicht** ausgefuehrt (kein `docker compose up`, keine Health-GET-Auszuege).

**DoD naechster Lauf:** `docker compose ps`, Stichprobe `GET /health` bzw. `scripts/healthcheck.sh`, pro Kernservice `docker compose logs --tail=200`, Prometheus targets „UP“, Auszug in neuer `RUN_*.md` **anhaengen**.

---

## PHASE 4 — UI/UX Totalpruefung

### Routen

- App-Pages: `AUDIT_EVIDENCE/ROUTE_INVENTORY_DASHBOARD.md`  
- BFF/API: `AUDIT_EVIDENCE/API_ROUTES_DASHBOARD.md`

### E2E (Playwright)

| Spec | Zweck |
|------|--------|
| `release-gate.spec.ts` | edge-status, Operator-Explain API, Kern-Konsole, Terminal |
| `trust-surfaces.spec.ts` | Trust-/Sicherheitsflaechen |
| `responsive-shell.spec.ts` | Shell responsiv |
| `broken-interactions.spec.ts` | Sidebar-Links + `/`, `/welcome` |

### Artefakte

- `BROKEN_LINKS.md` — Abdeckung Sidebar + dokumentierte Restrisiken  
- `BROKEN_BUTTONS.md` — Locale-Mirror geloggt; Klick-Matrix Self-Healing/Explain **offen** (P1-2)  
- `INCOMPLETE_PAGES.md` — Matrix + Diagnose/Self-Healing Hinweise

**FAIL gegen „jeder Button/Link“:** In-Page-Links, dynamische IDs, Admin-only ohne Nav, Form-Submits — **nicht** vollautomatisch abgedeckt.

---

## PHASE 5 — Marktuniversum

- **Konfiguration:** `BITGET_UNIVERSE_SYMBOLS`, Watchlist, Scopes in Compose/ENV — **datengetrieben**.  
- **Families (spot/margin/futures):** im Code/Gateway zu verifizieren; ohne Produkt-Spec hier **unvollstaendig** dokumentiert → **RISK**.  
- **Skalierung:** Caching/Pagination/Virtualisierung im UI teils offen (`PAGE_COMPLETION_MATRIX.md`).  
- **Pro-Symbol-Vollstaendigkeit (Chart, Orderbook, Signals, News, Performance):** **nicht** fuer beliebiges Symbol garantiert ohne Gateway-Faehigkeit + UI-Verdrahtung — **FAIL** bis nachgewiesen.

---

## PHASE 6 — KI Totalpruefung

### Inventar (kurz)

- Orchestrator `services/llm-orchestrator`; Schemas `shared/contracts/schemas`; Prompts `shared/prompts`; BFF `apps/dashboard/src/app/api/**/llm/**` und verwandte Routen; Fake-Provider lokal per ENV.  
- Eval: `tools/run_llm_eval.py`, `tests/llm_eval`, CI `validate_eval_baseline.py`.

### Qualitaet

- **Guardrails:** JSON-Schema + Envelope — gut, aber nicht gleich **Nutzerqualitaet 10/10**.  
- **Regression:** CI kann Baseline pruefen; **kein** Nachweis in diesem Lauf, dass alle Use-Cases **>= Zielscore** sind.

### KI_SCORECARD / KI_BACKLOG

Siehe `AUDIT_SCORECARD.md` (Abschnitt KI) und `AUDIT_BACKLOG.md` (P1-5, Sprint D).

---

## PHASE 7 — Security / Compliance / Fehlermeldungen

- **Secrets:** Server-only Keys, keine `NEXT_PUBLIC_*`-Secret-Namen (Validator); vollstaendiger Secret-Scan **nicht** in diesem Lauf.  
- **Fehlerkommunikation:** Gateway-Bootstrap, Product Messages, Diagnose, Self-Healing, Situation-Explain — **stark**; segmentierte React Error Boundaries **nicht** flaechendeckend verifiziert.  
- **Silent error classes:** Body-Parse `.catch(() => ({}))` — Risiko **niedrig**, wenn UI-Fehlerpfad existiert; weiter pruefen.  
- **UX-unakzeptabel:** Leere Main-Flaechen ohne Ursache+Fix-Pfad (Einzelscreens in Matrix noch offen).

---

## PHASE 8 — Deliverables & Plan Prompt B

| Artefakt | Pfad |
|----------|------|
| Scorecard | `docs/audit/AUDIT_SCORECARD.md` |
| Backlog | `docs/audit/AUDIT_BACKLOG.md` |
| Sprint-Detail | `docs/audit/SPRINT_PLAN.md` |
| Evidence | `docs/audit/AUDIT_EVIDENCE/*` |

**Plan Prompt B:** siehe `AUDIT_BACKLOG.md` (Sprints A–F) und `SPRINT_PLAN.md` — Prioritaet: echte Datenlage sichtbar (Stack-Smoke, Health), dann KI-Eval-Gates, dann Skalierung.

---

## Top-Findings (konsolidiert)

1. Kein Stack-/Log-Nachweis in diesem Prompt-A-Lauf auf dem Host.  
2. E2E gut fuer Kernpfade + Sidebar; nicht „alle Interaktionen“.  
3. KI: Infrastruktur ja, Ziel 10/10 pro Use-Case ohne Evidenz **FAIL**.  
4. Marktuniversum: ENV-skaliert; UI/Perf/Vollstaendigkeit **Luecken**.  
5. Remote-CI: als wahrscheinlich gruen anzunehmen, lokal hier **nicht** erneut verifiziert.  
6. Grafana/Prometheus: in Compose; Runbooks/Alerts **unverifiziert**.  
7. Zwei Betriebsmodi Dashboard (Compose vs. `pnpm dev`) — Betriebsdoku pflegen.  
8. Forensic-Routen und dynamische IDs: Stichproben noetig.  
9. i18n-Reste laut Matrix (Paper, News, Strategies).  
10. P1-3: weiteres Grep nach leeren Fehlerpfaden in anderen Paketen (`e2e/`, `shared/`).

---

*Ende Vorbericht. Naechster wiederholbarer Schritt: `RUN_YYYY-MM-DD.md` anreichern + Phase 3 dynamisch ausfuehren.*
