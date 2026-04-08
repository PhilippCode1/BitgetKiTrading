# AUDIT_SCORECARD — bitget-btc-ai

**Skala:** 0–11 (11 = „ueberperfekt“ laut Prompt-Definition).  
**Stand:** 2026-04-07 · **Prompt A Runde 3** · **Git HEAD:** `85404cd6488c5cfce6a37636d7c7fb34e1dac96b` (`master`, clean).  
**Hinweis:** Laufzeit-Stack und volles E2E auf diesem Host **nicht** gelaufen; Scores fuer Backend-Pipeline/SRE/KI bleiben **ceiling-begrenzt**. Stuetze: `AUDIT_EVIDENCE/RUN_2026-04-07_PROMPT_A_ROUND3.md`.

| # | Domäne | Score | Kurzbegründung | Evidenz / Anker |
|---|--------|------:|----------------|-----------------|
| 1 | **Repo-Hygiene & Versionsdisziplin** | **8** | Mehrere fokussierte Commits, sauberer Tree; Remote-CI/Tags beim Push weiter verifizieren. | `git log`, `BRANCH_AND_COMMIT_POLICY.md` |
| 2 | **Reproduzierbarkeit (Dev/Compose/ENV)** | **7** | `compose config` + `validate_env_profile` + `check-types` gruen; kein `compose up` hier. | `RUN_2026-04-07_PROMPT_A_ROUND3.md` |
| 3 | **Backend-Services (Worker)** | **6** | Architektur klar; Drops/Latenz ohne Runtime-Logs unbelegt. | `docker-compose.yml`, `services/*` |
| 4 | **API-Gateway** | **6** | Zentrale Rolle; kein Contract-Smoke in diesem Lauf. | `services/api-gateway` |
| 5 | **Datenpipelines (Markt → Signal)** | **6** | Compose-Kette; degraded/empty nicht gemessen. | `ai-architecture.md` |
| 6 | **Marktuniversum & Symbolskalierung** | **8** | Gateway-Status + Registry; UI: **Lineage-Panel** (Stream/Broker/Reconcile/Kernsymbole), **Pagination** `universePage`/`registryPage`; Chart/Orderbook/News pro beliebigem Symbol weiter **nicht** garantiert. | `market-universe/page.tsx`, `RUN_SPRINT2_2026-04-07.md` |
| 7 | **Dashboard / Frontend** | **8** | Marktuniversum-Transparenz verbessert; Terminal/Signals gleiche Dichte **offen**; Matrix-i18n-Reste. | `PAGE_COMPLETION_MATRIX.md` |
| 8 | **Routen / Links / Buttons (E2E Total)** | **6** | Vier Specs; Release-Gate inkl. `market-universe-lineage`; kein Full-Crawl, keine Button-Matrix. | `e2e/tests/*.spec.ts` |
| 9 | **Fehlerkommunikation & Self-Healing** | **7** | Produktmuster stark; verbleibende Body-parse-catches pruefen. | `best-effort-fetch.ts`, Diagnose-UI |
|10 | **Observability / SRE / MTTR** | **7** | Prometheus/Grafana; Alarm→Runbook nicht in diesem Lauf belegt. | `OBSERVABILITY_AND_SLOS.md` |
|11 | **KI: Qualität, Evals, Guardrails** | **6** | Tooling + CI-Baseline; kein frischer Eval-Lauf = kein 10/10. | `tools/run_llm_eval.py`, `tests/llm_eval` |
|12 | **Security / Compliance** | **7** | Validator + Matrix; kein Pentest/Secrets-Scan diesmal. | `tools/validate_env_profile.py` |

## KI-Teil-Scorecard (Use-Cases, Ziel ≥10)

| Use-Case | Score | Warum nicht 10+ |
|----------|------:|-----------------|
| Operator Explain | **6** | Schema ok; messbare Regression = Eval + Nutzer-Fehlerbilder. |
| Strategy / Signal Explain | **6** | Analog. |
| Safety / Incident Diagnose | **6** | Route ok; Golden-Set fehlt in Evidenz. |
| Assist Layer | **5** | Breite ohne Eval-Katalog. |
| AI Strategy Proposal Drafts | **5** | Determinismus teils; End-to-End-Qualitaet offen. |

## Gesamteinschätzung (ehrlich)

**Fortschritt bei Marktuniversum-Transparenz und Repo-Disziplin; Gesamtbild weiter 6–8:** Ohne **laufenden Stack**, **flaechendeckendes E2E** und **KI-Eval-Artefakte** kein Gesamturteil 9–11.
