# AUDIT_SCORECARD — bitget-btc-ai

**Skala:** 0–11 (11 = „ueberperfekt“ laut Prompt-Definition).  
**Stand Report:** 2026-04-07 (nach Sprint 2 Teil) · **Git HEAD:** `a511b8c` (`master`).  
**Hinweis:** Scores **>8** fuer Laufzeit/E2E/KI setzen einen **nachweisbaren** gruenen Stack- bzw. Eval-Lauf voraus — dieser Prompt-A-Lauf lieferte **statische** Checks + `pnpm check-types` + `validate_env_profile` + `docker compose config`.

| # | Domäne | Score | Kurzbegründung | Evidenz / Anker |
|---|--------|------:|----------------|-----------------|
| 1 | **Repo-Hygiene & Versionsdisziplin** | **7** | Commits auf `master`; Policy `BRANCH_AND_COMMIT_POLICY.md`; Remote-CI/Tags beim Push verifizieren. | `RUN_2026-04-07.md`, `RUN_SPRINT1_2026-04-08.md` |
| 2 | **Reproduzierbarkeit (Dev/Compose/ENV)** | **7** | Compose-Config valide; Validator OK (CI-Style-ENV); Scripts inventarisiert; **Stack-Up** auf diesem Host nicht gelaufen. | `docker-compose.yml`, `package.json`, `RUN_2026-04-07.md` |
| 3 | **Backend-Services (Worker)** | **6** | Architektur + Dockerfiles; ohne Runtime-Logs keine Drop-/Latency-Belege. | `services/*`, `docker-compose.yml` |
| 4 | **API-Gateway** | **6** | Zentrale Rolle + Dashboard-BFF; Contract-Smoke hier nicht ausgefuehrt. | `services/api-gateway`, `apps/dashboard` |
| 5 | **Datenpipelines (Markt → Signal)** | **6** | Compose-Kette plausibel; Datenqualitaet/degraded nicht gemessen. | `ai-architecture.md` |
| 6 | **Marktuniversum & Symbolskalierung** | **7** | ENV-gesteuert; UI-Perf und „alles pro Symbol“ unvollstaendig. | `PAGE_COMPLETION_MATRIX.md` |
| 7 | **Dashboard / Frontend** | **7** | Umfangreich, Diagnose/Self-Healing; Matrix-Schulden. | `apps/dashboard` |
| 8 | **Routen / Links / Buttons (E2E Total)** | **6** | + Release-Gate prueft Marktuniversum-Lineage; Full-Crawl/Button-Matrix offen. | `release-gate.spec.ts` |
| 9 | **Fehlerkommunikation & Self-Healing** | **7** | Starke Muster; Locale-Mirror mit Warn-Log; nicht alle Pfade verifiziert. | `best-effort-fetch.ts`, Diagnose-Komponenten |
|10 | **Observability / SRE / MTTR** | **7** | Prometheus/Grafana in Compose; Alarm→Runbook nicht in diesem Lauf belegt. | `OBSERVABILITY_AND_SLOS.md` |
|11 | **KI: Qualität, Evals, Guardrails** | **6** | Schema/Orchestrator/Eval-Tooling/CI-Baseline; kein frischer Eval-Nachweis hier. | `tools/run_llm_eval.py`, `tests/llm_eval` |
|12 | **Security / Compliance** | **7** | ENV-Matrix + Validator; `--help` Windows-sicher; kein Pentest/Secrets-Scan diesmal. | `tools/validate_env_profile.py` |

## KI-Teil-Scorecard (Use-Cases, Ziel ≥10)

| Use-Case | Score | Warum nicht 10+ |
|----------|------:|-----------------|
| Operator Explain | **6** | Strukturiert; messbare Regression = Eval + Gate + Stichprobe UX. |
| Strategy / Signal Explain | **6** | Analog; Eval-Pflicht. |
| Safety / Incident Diagnose | **6** | Route vorhanden; Qualitaet ohne Golden-Set **unbelegt**. |
| Assist Layer | **5** | Breit; Eval-Katalog fehlt. |
| AI Strategy Proposal Drafts | **5** | Determinismus/Promotion-Tests teils vorhanden; End-to-End-Qualitaet offen. |

## Gesamteinschätzung (ehrlich)

**Architektur und Tooling sind professionell; Ausfuehrungs- und Evidenzluecken verhindern 9–11:** Git und statische Checks sind in Ordnung; **Laufzeit, flaechendeckende UI-Interaktionen und KI-Metriken** muessen in Folgelaeufen **nachgewiesen** werden (`AUDIT_EVIDENCE/RUN_*.md`).
