# AUDIT_REPORT — Vorbericht (Totalaudit Prompt A)

**Datum:** 2026-04-08  
**Branch:** `master`  
**Commit-Hash:** *keiner* — Working Tree vollständig untracked (siehe `AUDIT_EVIDENCE/RUN_2026-04-08.md`).  
**Umfeld:** Windows 10, PowerShell; Audit aus Cursor-Agent-Lauf; **Docker-Stack und `pnpm e2e` in diesem Lauf nicht gestartet** (statische Analyse + Skript-Inventar).

---

## Executive Summary

Das Repository `bitget-btc-ai` beschreibt eine **vollständige Zielarchitektur** (Marktstream → Features → Struktur → Zeichnung → Signale → Broker → API-Gateway → Dashboard) mit **docker-compose-orchestrierter Laufzeit**, **Observability-Stack** (Prometheus/Grafana), **strukturierten LLM-Antworten** (JSON-Schema + Orchestrator) und einem **umfangreichen Next.js-Dashboard** inkl. Diagnose, Self-Healing und KI-gestützter Situationserklärung.

**Harte Lücken für ein „kompromissloses“ Go-Live-Urteil:**

1. **Keine Git-Baseline** (null Commits) — Reproduzierbarkeit und Audit-Trail fehlen formal.  
2. **Kein dynamischer Nachweis** in diesem Lauf: Health/Ready-Checks, Service-Logs, E2E-JUnit, LLM-Eval-Artefakte.  
3. **UI-Totalprüfung** ist **nicht** durch automatischen Link-Crawler abgedeckt; Playwright deckt ein **Subset** ab.  
4. **KI-Ziel 10/11** ist **nicht** belegbar ohne laufende Evals, Golden-Sets und Fehlerquoten-Metriken pro Use-Case.

---

## PHASE 1 — Baseline & Reproduzierbarkeit

### Git

- `git status`: Branch `master`, **No commits yet**, alle Pfade untracked.  
- `git diff`: nicht anwendbar ohne Commits.

### package.json (Root) — Scripts (Auszug, vollständig siehe Datei)

Wichtige Kategorien:

- **Monorepo:** `dev`, `build`, `lint`, `test`, `check-types`, `format`  
- **Stack:** `dev:up`, `dev:down`, `stack:check`, `local:doctor`, `rc:health`  
- **Konfiguration:** `config:validate`, `config:validate:production`, `config:validate:shadow`  
- **E2E:** `e2e`, `e2e:ui`, `e2e:debug`, `e2e:install`  
- **KI-Eval:** `llm:eval` → `python tools/run_llm_eval.py`  
- **Python:** `py:check`, `py:test`, `py:cov`

### Docker Compose

- **Datei:** `docker-compose.yml` (Root).  
- **Services (Kernkette):** `redis`, `postgres`, `market-stream`, `feature-engine`, `structure-service`, `drawing-service`, `signal-engine`, `live-broker`, `api-gateway`, `llm-orchestrator`, `prometheus`, `grafana`, optional `dashboard` (Profil `with-dashboard`).  
- **Ports (typisch):** Redis 6379, Postgres 5432, Market-Stream 8001, Feature 8002, Structure 8003, Drawing 8004, Signal 8005, Live-Broker 8006, API-Gateway 8080, LLM-Orchestrator 8010, Prometheus 9090, Grafana 3000, Dashboard 3001.  
- **ENV:** Umfangreiche `BITGET_*`, `POSTGRES_*`, `REDIS_*`, Universe-/Watchlist-/Scope-Variablen — siehe Compose `environment`-Blöcke.

### ENV-Profile

- Vorhanden: `.env.example`, `.env.local.example`, `.env.production.example`, `.env.shadow.example`, `.env.test.example`.  
- Validator: `tools/validate_env_profile.py` — in einem früheren Lauf `--help`-Kontext mit Pflichtparametern problematisch; als **P2-Backlog** (`AUDIT_BACKLOG.md`).

### Reproduktions-Setup (empfohlen)

1. `pnpm install`  
2. `pnpm config:validate` (mit passender `.env.local`)  
3. `pnpm dev:up` oder `docker compose --profile with-dashboard up -d`  
4. `pnpm rc:health` / `pnpm local:doctor`  
5. `pnpm e2e` mit `E2E_BASE_URL` und ggf. `E2E_AUTH_COOKIE`  
6. `pnpm llm:eval` (wenn API-Keys gesetzt)

---

## PHASE 2 — Architektur & Verdrahtung (statisch)

### Systemübersicht

| Komponente | Rolle |
|------------|--------|
| `market-stream` | Bitget-Stream → Redis/Downstream |
| `feature-engine` | Features aus Marktdaten |
| `structure-service` | Struktur-Erkennung |
| `drawing-service` | Chart-/Zeichenlogik |
| `signal-engine` | Signalerzeugung |
| `live-broker` | Ausführung/Bridge (PAPER/SHADOW/LIVE je Policy) |
| `api-gateway` | Zentraler HTTP-Einstieg, Routing zu Worker-Services |
| `llm-orchestrator` | Strukturierte LLM-Aufrufe (Schemas) |
| `apps/dashboard` | Next.js BFF + UI (`/console`, `/api/...`) |

### Datenfluss (Zielbild)

`Market-Stream` → `Feature` → `Structure` → `Drawing` → `Signal` → `Live-Broker` → `API-Gateway` → `Dashboard` (Server Components + Client).

### Events / Queues

- Redis als zentraler Bus (Streams/Keys je Service — Detail in Service-READMEs und `ai-architecture.md`).  
- **Drop-Risiko:** ohne Laufzeit-Logs nicht quantifizierbar; in Backlog P1.

### Ungenutzte / halbe Services

- Compose-Profil `with-dashboard` trennt Dashboard-Container von lokalem `pnpm dev` — kein „toter“ Service, aber **zwei** Betriebsmodi zu dokumentieren.  
- Einzelne `services/*` mit minimalen Implementierungen: gezielter Code-Walk nötig in Prompt B.

---

## PHASE 3 — Laufzeit-Check (dynamisch)

**Status in diesem Audit:** **Nicht ausgeführt.**

Empfohlene Evidenz für nächsten Lauf:

- `docker compose ps`  
- `curl`/`pnpm rc:health` Ausgabe  
- Pro-Service `docker compose logs --tail=200 <service>`  
- Screenshot Grafana/Prometheus Targets „UP“

→ Artefakte unter `docs/audit/AUDIT_EVIDENCE/RUN_<datum>.md` anhängen.

---

## PHASE 4 — UI/UX Totalprüfung

### Routen

- Dashboard: siehe `AUDIT_EVIDENCE/ROUTE_INVENTORY_DASHBOARD.md`  
- API-Routen (App Router): siehe `AUDIT_EVIDENCE/API_ROUTES_DASHBOARD.md`

### Crawl / E2E

- Playwright: `e2e/tests/release-gate.spec.ts`, `trust-surfaces.spec.ts`, `responsive-shell.spec.ts` (+ ggf. weitere).  
- **Kein** vollständiger Link-Graphen-Crawler in diesem Repo-Zustand verifiziert.

### Artefakte

| Datei | Inhalt |
|-------|--------|
| `BROKEN_LINKS.md` | Platzhalter bis Crawl |
| `BROKEN_BUTTONS.md` | Platzhalter bis Matrix |
| `INCOMPLETE_PAGES.md` | Verweis auf `PAGE_COMPLETION_MATRIX.md` + bekannte Lücken |

---

## PHASE 5 — Marktuniversum

- **Modellierung:** Über Compose-ENV (`BITGET_UNIVERSE_SYMBOLS`, Watchlist, Scopes) und Gateway-Konfiguration — **datengetrieben** skalierbarer als reine Hardcodes im UI.  
- **UI:** `market-universe`, Chart-Kontext, Signal-Center — Matrix nennt Performance-Risiken bei sehr vielen Instrumenten (Pagination/Virtualisierung).  
- **Vollständigkeit pro Symbol:** Nicht jede Unterseite garantiert Chart+Orderbook+News+Performance für beliebiges Symbol ohne weitere Integrationsarbeit — teils **FAIL** bis nachgewiesen.

---

## PHASE 6 — KI-Totalprüfung

### Inventar

- **Orchestrator:** `services/llm-orchestrator`  
- **Schemas:** `shared/contracts/schemas` (z. B. `operator_explain`)  
- **Prompts:** `shared/prompts` (Manifest)  
- **Dashboard-BFF:** `apps/dashboard/src/app/api/llm/*`, `assist/[segment]`, Operator/Strategy-Pfade  
- **Eval:** `tools/run_llm_eval.py` → Ausgabe unter `artifacts/llm_eval/`, Tests unter `tests/llm_eval`

### Qualität

- Strukturierte JSON-Ausgabe + Validierung ist **Grundlage** für Guardrails.  
- **Messbarkeit:** Erfordert regelmäßige Eval-Läufe + Schwellen in CI — **nicht** in diesem Audit belegt.

Detaillierte Teil-Scores: `AUDIT_SCORECARD.md` (Abschnitt KI).

---

## PHASE 7 — Security / Compliance / Fehlerkommunikation

- **Secrets:** Server-only Env für Bitget/JWT dokumentiert in Projektguides; keine Keys in Repo-Beispielen erwünscht — **Scan in diesem Lauf nicht ausgeführt**.  
- **Fehler-UX:** Product Messages, Situation Bar, Self-Healing, Diagnose-Zentrale — stark.  
- **Silent errors:** vereinzelte leere `catch` — Backlog P1-3.

---

## PHASE 8 — Verweise auf Deliverables

| Artefakt | Pfad |
|----------|------|
| Scorecard | `docs/audit/AUDIT_SCORECARD.md` |
| Backlog + Prompt-B-Plan | `docs/audit/AUDIT_BACKLOG.md` |
| Evidenz-Index | `docs/audit/AUDIT_EVIDENCE/README.md` |
| Lauf-Notiz | `docs/audit/AUDIT_EVIDENCE/RUN_2026-04-08.md` |

---

## Anhang: Top-Findings (kurz)

1. Kein Git-Commit — P0.  
2. Kein Stack/E2E-Lauf in diesem Audit — dynamische Scores unbelegt.  
3. Link/Button-Totalcoverage fehlt — P1.  
4. KI ohne Eval-Nachweis — max. Score 6–7.  
5. Marktuniversum skalierbar per ENV; UI-Perf bei N→∞ offen.  
6. `validate_env_profile.py` CLI-UX verbesserungsfähig.  
7. Zwei Dashboard-Betriebsmodi (Compose vs. pnpm) — Dokumentationspflicht.  
8. `PAGE_COMPLETION_MATRIX.md` listet noch i18n-/Tabellen-Schulden.  
9. Prometheus/Grafana vorhanden; Alerting-Runbooks nicht in diesem Report verifiziert.  
10. Self-Healing + Diagnose + Situation-AI — starke Säule, weiter mit Tests absichern.

---

*Ende Vorbericht. Nächster Schritt: Prompt B — P0/P1 aus `AUDIT_BACKLOG.md` abarbeiten und Evidenz in `AUDIT_EVIDENCE/` anreichern.*
