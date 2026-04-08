# AUDIT_SCORECARD — bitget-btc-ai

**Skala:** 0–11 (11 = „überperfekt“ laut Prompt-Definition).  
**Stand:** 2026-04-08 (Sprint 1 Prompt B) · **Git:** Initial-Commit ausstehend bis `git commit` auf dem Rechner des Teams.  
**Hinweis:** E2E-Sidebar-Coverage neu; voller Stack-/Playwright-Nachweis weiterhin **CI-lokal** zu bestätigen.

| # | Domäne | Score | Kurzbegründung | Evidenz / Anker |
|---|--------|------:|----------------|-----------------|
| 1 | **Repo-Hygiene & Versionsdisziplin** | **3** | Branch-Policy dokumentiert (`BRANCH_AND_COMMIT_POLICY.md`); Commit-Pflicht unveraendert bis ausgefuehrt. | `RUN_SPRINT1_2026-04-08.md` |
| 2 | **Reproduzierbarkeit (Dev/Compose/ENV)** | **6** | `docker-compose.yml` mit vollständiger Engine-Kette + Healthchecks; Root-`package.json` mit `dev:up`, `config:validate*`, `stack:check`, `local:doctor`. ENV-Profile dokumentiert (`.env.*.example`). Lauf **nicht** verifiziert. | `docker-compose.yml`, `package.json` |
| 3 | **Backend-Services (Worker)** | **6** | 13 Dockerfiles unter `services/*`, klare Pipeline-Zuordnung (market-stream → … → gateway). Ohne Runtime: keine Aussage zu Drops, Backpressure, realen Metriken. | `services/*/Dockerfile`, `docker-compose.yml` |
| 4 | **API-Gateway** | **6** | Eigenes Image, zentrale Rolle; BFF `gateway/[...segments]` im Dashboard. Contract-Tests nicht in diesem Lauf ausgeführt. | `apps/dashboard/.../gateway`, `services/api-gateway` |
| 5 | **Datenpipelines (Markt → Signal)** | **6** | Architektur in Compose abgebildet; Datenqualität/„degraded“ nur über Docs + Health-Pfade belegbar, nicht gemessen. | `ai-architecture.md`, `OBSERVABILITY_AND_SLOS.md` |
| 6 | **Marktuniversum & Symbolskalierung** | **7** | Compose-Defaults `BITGET_UNIVERSE_SYMBOLS` / WATCHLIST / FEATURE_SCOPE / SIGNAL_SCOPE — datengetrieben statt nur Hardcode im Chart; UI-Matrix nennt noch Performance-Risiken bei sehr vielen Instrumenten. | `docker-compose.yml`, `PAGE_COMPLETION_MATRIX.md` |
| 7 | **Dashboard / Frontend** | **7** | Viele Routen, Product-Message-Pattern, Live-Datenlage, Diagnose/Self-Healing, KI-Erklärblock; verbleibende i18n-/Tabellen-Schulden in Matrix. | `apps/dashboard`, `PAGE_COMPLETION_MATRIX.md` |
| 8 | **Routen / Links / Buttons (E2E „totale“ Abdeckung)** | **6** | + `broken-interactions.spec.ts` (Sidebar-Traversal); Gesamt-UI-Crawl / Klick-Matrix weiter P1. | `e2e/tests/broken-interactions.spec.ts`, `BROKEN_LINKS.md` |
| 9 | **Fehlerkommunikation & Self-Healing** | **7** | Locale-Mirror: Warn-Logs statt stillem Catch; uebrige silent-catch-Stellen Grep-offen. | `best-effort-fetch.ts`, Matrix |
|10 | **Observability / SRE / MTTR** | **7** | Prometheus/Grafana in Compose; Docs zu SLOs; Health/ready-Routen. Kein Laufzeit-Nachweis Alarmierung→Runbook in diesem Audit. | `docker-compose.yml`, `OBSERVABILITY_AND_SLOS.md` |
|11 | **KI: Qualität, Evals, Guardrails** | **6** | Orchestrator + JSON-Schema (`operator_explain`), BFF-Routen, `tools/run_llm_eval.py` → `tests/llm_eval`, Prompt-Manifest unter `shared/prompts`. **Kein** ausgeführter Eval-Lauf hier; kein Nachweis „10/10“ pro Use-Case. | `services/llm-orchestrator`, `shared/contracts/schemas`, `tools/run_llm_eval.py` |
|12 | **Security / Compliance** | **7** | Server-only Secrets fuer Gateway/JWT dokumentiert; ENV-Validator; `--help` Windows/cp1252-sicher. Volle Pentest-Evidenz fehlt. | `LANGUAGE_AND_UX_GUIDE.md`, `tools/validate_env_profile.py` |

## KI-Teil-Scorecard (Use-Cases, Ziel ≥10)

| Use-Case | Score | Warum nicht 10+ |
|----------|------:|-----------------|
| Operator Explain | **6** | Strukturiertes Schema, Retrieval-Tags; Antworttext nicht in 7 Felder gesplittet; Regression nur wenn `tests/llm_eval` + Orchestrierung grün. |
| Strategy / Signal Explain | **6** | Eigene Route + Schema analog; gleiche Eval-Abhängigkeit. |
| Safety / Incident Diagnose | **6** | Pfad vorhanden; messbare Qualität = Eval + Human-Review. |
| Assist Layer (`assist/[segment]`) | **5** | Breite Oberfläche; ohne Eval-Katalog schwer belastbar. |
| AI Strategy Proposal Drafts | **5** | Geschäftskritisch; braucht deterministische Checks + Promotion-Flow-Tests (Teilweise Routen `validate-deterministic`). |

## Gesamteinschätzung (ehrlich)

**Production-nahe Architektur mit lückenhaft belegter Ausführung:** Code und Compose sind reif genug für ein professionelles Zielbild; **Git-Baseline fehlt**, **dynamische Beweise fehlen** — das blockiert ein echtes 9–10 Gesamturteil.
