# AUDIT_SCORECARD — bitget-btc-ai

**Skala:** 0–11 (11 = „überperfekt“ laut Prompt-Definition).  
**Stand:** 2026-04-08 · **Prompt B Sprint 1** (nach Prompt A Runde 4).  
**Evidence:** `RUN_PROMPT_B_SPRINT1_2026-04-08.md`, `RUN_2026-04-07_PROMPT_A_ROUND4.md`, `pytest tests/llm_eval` (weiterhin 23 passed bei Lauf).  
**Neu:** `pnpm rc:health` + `docker compose ps` healthy; **E2E broken-interactions** nach Dashboard-Rebuild erwartet grün (Hydration #418 behoben).

| # | Domäne | Score | Kurzbegründung | Evidenz / Anker |
|---|--------|------:|----------------|-----------------|
| 1 | **Repo-Hygiene & Versionsdisziplin** | **8** | Fokussierte Historie; **aktuell dirty** — Disziplin-Minus bis Commit. | `git status`, `BRANCH_AND_COMMIT_POLICY.md` |
| 2 | **Reproduzierbarkeit (Dev/Compose/ENV)** | **8** | Stack healthy + `rc:health` OK; `check-types` grün; vollständiges `config:validate` gegen Prod-`.env` weiter optional. | `RUN_PROMPT_B_SPRINT1_2026-04-08.md` |
| 3 | **Backend-Services (Worker)** | **6** | Architektur klar; Drops/Latenz/Health ohne laufenden Stack unbelegt. | `docker-compose.yml`, `services/*` |
| 4 | **API-Gateway** | **6** | Zentrale Rolle; kein Contract-Smoke in Runde 4. | `services/api-gateway` |
| 5 | **Datenpipelines (Markt → Signal)** | **6** | Compose-Kette dokumentiert; degraded/empty nicht gemessen. | `ai-architecture.md` |
| 6 | **Marktuniversum & Symbolskalierung** | **8** | Lineage-Panel, Pagination, Kernsymbole; **500+-Lasttest** fehlt; „beliebiges Symbol“-Produktpaket nicht garantiert. | `market-universe`, `RUN_SPRINT2_2026-04-07.md` |
| 7 | **Dashboard / Frontend** | **9** | MU-Transparenz stark; **WT:** Terminal/Signals gleiche Health-Lineage — bis Merge weiterhin Risiko für „released“ Stand. | `PlatformExecutionStreamsGrid` (WT), `PAGE_COMPLETION_MATRIX.md` |
| 8 | **Routen / Links / Buttons (E2E Total)** | **8** | Sidebar + **kritische Pfade** + **sichere Klicks** in `broken-interactions.spec.ts`; Full-In-Page-Crawl + P1-2 offen. | `e2e/tests/broken-interactions.spec.ts` |
| 9 | **Fehlerkommunikation & Self-Healing** | **7** | Produktmuster stark; verbleibende `.catch`-Pfade (7 Dateien mit mindestens einem Catch) reviewen. | Grep `.catch(` in `apps/dashboard/src` |
|10 | **Observability / SRE / MTTR** | **7** | Prometheus/Grafana im Compose; Alarm→Runbook in Runde 4 nicht belegt. | `OBSERVABILITY_AND_SLOS.md` |
|11 | **KI: Qualität, Evals, Guardrails** | **7** | **`pytest tests/llm_eval` 23/23** lokal; Tooling + Schemas vorhanden — **kein** 10/11 ohne Nutzer-Qualitätsmetrik, Produktions-Fehlerquote, CI-Artefakt in diesem Lauf. | `tools/run_llm_eval.py`, `tests/llm_eval` |
|12 | **Security / Compliance** | **7** | Validator + Matrix; kein Pentest/Secrets-Scan Runde 4. | `tools/validate_env_profile.py` |

## KI-Teil-Scorecard (Use-Cases, Ziel ≥10)

| Use-Case | Score | Warum nicht 10+ |
|----------|------:|-----------------|
| Operator Explain | **7** | Regression-Tests grün; echte Provider-Qualität / Latenz / Nutzerverständlichkeit ungemessen. |
| Strategy / Signal Explain | **7** | Analog. |
| Safety / Incident Diagnose | **7** | Testabdeckung im Repo; Feld-Fehlerbilder fehlen in Evidence. |
| Assist Layer | **6** | Breite ohne produktnahe Eval-Kennzahlen. |
| AI Chart Annotations | **7** | `test_eval_chart_annotations` u. a. — UI-Integration abhängig von Gateway-Daten. |

## Gesamteinschätzung (ehrlich)

**Fortschritt:** Statische Qualität (`check-types`, `llm_eval` pytest) und UI-Transparenz (MU; Terminal/Signals im WT). **Gesamtbild weiter 6–9:** Ohne **laufenden Stack**, **E2E gegen Deploy**, **ENV-Validate-Nachweis** und **KI-Nutzer-Metriken** kein Gesamturteil 10–11.

---

## Archiv — Runde 3 (Referenz)

| # | Domäne | Score (R3) |
|---|--------|----------:|
| 1 | Repo-Hygiene | 8 |
| 2 | Reproduzierbarkeit | 7 |
| 3–5 | Backend / Gateway / Pipelines | 6 |
| 6 | Marktuniversum | 8 |
| 7 | Dashboard | 8 |
| 8 | Routen E2E | 6 |
| 9 | Fehlerkommunikation | 7 |
|10 | Observability | 7 |
|11 | KI | 6 |
|12 | Security | 7 |

*HEAD Runde 3:* `85404cd6488c5cfce6a37636d7c7fb34e1dac96b` (clean). Evidence: `RUN_2026-04-07_PROMPT_A_ROUND3.md`.
