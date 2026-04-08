# AUDIT_SCORECARD — bitget-btc-ai

**Skala:** 0–11 (11 = „überperfekt“ laut Prompt-Definition).  
**Stand:** 2026-04-08 · **Prompt A Runde 5** · **Git HEAD:** `e871b871b4a8cd803edcec50ca763e50cad7078c` (`master`, clean).  
**Evidence:** `AUDIT_EVIDENCE/RUN_2026-04-08_PROMPT_A_ROUND5.md`, `RUN_PROMPT_B_SPRINT1_2026-04-08.md`, `RUN_2026-04-07_PROMPT_A_ROUND4.md`

| # | Domäne | Score | Kurzbegründung | Evidenz / Anker |
|---|--------|------:|----------------|-----------------|
| 1 | **Repo-Hygiene & Versionsdisziplin** | **9** | Tree clean; fokussierte Commits (`42fe623`, `e871b87`). | `git status` |
| 2 | **Reproduzierbarkeit (Dev/Compose/ENV)** | **7** | `compose config` + `check-types` grün; **`rc:health` in R5 instabil** (Redis); `config:validate` vollständig offen. | `RUN_2026-04-08_PROMPT_A_ROUND5.md` |
| 3 | **Backend-Services (Worker)** | **5** | Architektur klar; **Laufzeit: mehrere Services „nicht ok“** wenn Edge leidet. | `rc:health`-Log R5 |
| 4 | **API-Gateway** | **5** | Zentrale Rolle; **`/ready` mit core_redis false** (Timeout) — kritisch. | Gateway payload in R5 |
| 5 | **Datenpipelines (Markt → Signal)** | **5** | Von Redis/Gateway abhängig; ohne stabile Edge unbelegt. | Phase 3 REPORT |
| 6 | **Marktuniversum & Symbolskalierung** | **8** | Lineage, Pagination, Kernsymbole; Lasttest 500+ offen; Pro-Symbol-Paket nicht garantiert. | `market-universe`, Sprint-2-Doku |
| 7 | **Dashboard / Frontend** | **9** | Hydration-Fix; MU + Terminal/Signale Lineage committed; Matrix-i18n-Reste. | `LiveDataSituationBar`, `PlatformExecutionStreamsGrid` |
| 8 | **Routen / Links / Buttons (E2E Total)** | **7** | Specs existieren (Sidebar + kritische Pfade + Klicks); **R5 kein grüner E2E-Lauf** dokumentiert. | `e2e/tests/broken-interactions.spec.ts` |
| 9 | **Fehlerkommunikation & Self-Healing** | **7** | Produktmuster stark; `.catch`-Review offen. | Dashboard-Grep |
|10 | **Observability / SRE / MTTR** | **6** | Prometheus/Grafana vorhanden; **Schwelle healthy vs. ready** verwirrt; Redis-Ausfall muss schneller sichtbar sein. | `OBSERVABILITY_AND_SLOS.md`, R5 |
|11 | **KI: Qualität, Evals, Guardrails** | **7** | **`pytest tests/llm_eval` 23/23** (R5); kein 10/11 ohne Nutzermetrik + CI-Artefakt. | `tests/llm_eval` |
|12 | **Security / Compliance** | **7** | Validator + Matrix; kein Pentest diesmal. | `validate_env_profile.py` |

## KI-Teil-Scorecard (Use-Cases, Ziel ≥10)

| Use-Case | Score | Warum nicht 10+ |
|----------|------:|-----------------|
| Operator Explain | **7** | Regression grün; Feldqualität/Latenz/SLO fehlen. |
| Strategy / Signal Explain | **7** | Analog. |
| Safety / Incident Diagnose | **7** | Tests im Repo; Evidence aus Produktion fehlt. |
| Assist Layer | **6** | Breite ohne Kennzahlen. |
| AI Chart Annotations | **7** | Abhängig von stabiler Marktdaten-Kette. |

## Gesamteinschätzung (ehrlich)

**Regression bei Laufzeit-Vertrauen (R5):** Redis/Gateway schwächt alles Downstream. **Statik + KI-Unit-Evals** bleiben stark; **SRE/Edge** muss vor nächstem Release hart stabilisiert werden — sonst kein Gesamturteil ≥8.

---

## Archiv — Scorecard Prompt B Sprint 1 / Runde 4

| Domäne | Score (kurz vor R5) |
|--------|---------------------|
| Repo | 8 (dirty → jetzt 9) |
| Repro | 8 → **7** (rc:health Flake) |
| Gateway | 6 → **5** |
| Worker | 6 → **5** |
| E2E | 8 → **7** (kein Lauf R5) |
| SRE | 7 → **6** |

---

## Archiv — Runde 3 (Referenz)

Siehe ältere `AUDIT_SCORECARD.md` in Git-Historie; HEAD R3 `85404cd…`.
