# AUDIT_BACKLOG — Priorisiert (Owner: Cursor / Team)

**P83 (2026-04-24):** Diese Datei ist **Sprint- und Runden-Historie** inkl. alter **Offen/Teil-**Einträge. **Technischer Produkt-DoD** (alle technischen Kästchen): [LaunchChecklist.md](../LaunchChecklist.md) und Master-Audit [SYSTEM_AUDIT_MASTER.md](../SYSTEM_AUDIT_MASTER.md). Tabellen unten ersetzen keine erneute Verifikation; sie dienen dem Nachvollzug älterer Runden (z. B. 2026-04-08 Redis-Evidence).

**Legende DoD:** Jede P0/P1-Story schließt mit **Testnachweis** (pytest/playwright/turbo) + **Doku-Update** in `docs/audit/AUDIT_EVIDENCE/`.

---

## Prompt A — Runde 5 (2026-04-08)

| Thema | Status | Evidence |
|-------|--------|----------|
| Baseline git + check-types | **Done** | `RUN_2026-04-08_PROMPT_A_ROUND5.md` |
| `pytest tests/llm_eval` | **Done** | 23 passed |
| `docker compose ps` | **Done** | Container healthy |
| `pnpm rc:health` stabil | **Done** (nach P0-0) | `AUDIT_EVIDENCE/RUN_P0-0_REDIS_READINESS.md`; Gateway-Image nach Fix neu bauen |
| E2E voll gegen :3000 | **Offen** | Nach Redis-Fix erneut `pnpm e2e` |

---

## KI_BACKLOG (Ziel 10/10 pro Use-Case — Owner: Cursor)

| ID | Thema | DoD | Testnachweis |
|----|-------|-----|--------------|
| KI-1 | **Operator Explain** — Nutzer-verständliche Fehler + Latenz-SLO | UI-Copy + BFF-Timeout dokumentiert; Feld-Log-Sampling | E2E Submit + `tests/llm_eval` |
| KI-2 | **Strategy/Signal Explain** — Golden-Set aus Produktions-Failures | `shared/prompts` + Manifest; Regression | `pytest tests/llm_eval` |
| KI-3 | **Safety-Diagnose** — deterministische Guardrails + Fallback | Kein leerer Erfolg bei Schema-Bruch | `test_eval_safety_diagnosis.py` |
| KI-4 | **CI-Gate** — Eval-Artefakt pro PR/Release | `artifacts/llm_eval/` + rot bei Baseline-Bruch | `.github/workflows` |
| KI-5 | **Metriken** — Fehlerquote / Tokens / Kosten Dashboard (intern) | Minimaler Export oder Log-Structured Counter | Runbook |

---

## Prompt A — Runde 4 (2026-04-07)

| Thema | Status | Evidence |
|-------|--------|----------|
| Statische Baseline | **Teil-Done** | `RUN_2026-04-07_PROMPT_A_ROUND4.md` — `compose config`, `pnpm check-types`, `pytest tests/llm_eval` (23 passed) |
| Stack + `rc:health` + Logs | **Done** | `RUN_PROMPT_B_SPRINT1_2026-04-08.md` |
| `pnpm e2e` + JUnit/HTML | **Teil** | Broken-interactions erweitert; grün nach `docker compose build dashboard` |
| Arbeitsbaum clean + Commit | **Done** | `42fe623` |

---

## Prompt A — Runde 3 (2026-04-07)

| Thema | Status | Evidence |
|-------|--------|----------|
| Report + Scorecard | Done | `AUDIT_REPORT.md`, `AUDIT_SCORECARD.md` (HEAD `85404cd…`) |
| Baseline-Befehle | Done | `RUN_2026-04-07_PROMPT_A_ROUND3.md` |
| Phase 3 dynamisch | **Offen** | Stack + Logs |

---

## Sprint 2 (Prompt B) — Stand

| ID | Status | Nachweis |
|----|--------|----------|
| Marktuniversum Datenpfad sichtbar | **Teil-Done** | `RUN_SPRINT2_2026-04-07.md`, Panel + Pagination |
| P1-4 Lastprofil 500+ Symbole | **Offen** | Nur Pagination UI; kein Lasttest-Dokument |
| Terminal/Signals gleiche Transparenz | **Done** | `RUN_SPRINT2b_TERMINAL_SIGNALS_LINEAGE.md`, `PlatformExecutionStreamsGrid`, Release-Gate testids |

---

## Prompt A — Lauf 2026-04-07 (Wiederholung)

| Thema | Status | Evidence |
|-------|--------|----------|
| Report/Scorecard aktualisiert | Done | `AUDIT_REPORT.md`, `AUDIT_SCORECARD.md` (HEAD `f09221a…`) |
| Baseline-Befehle | Done | `AUDIT_EVIDENCE/RUN_2026-04-07.md` (`check-types`, `validate_env_profile`, `docker compose config`) |
| Phase 3 dynamisch | **Offen** | Stack + Logs in neuer `RUN_*.md` |

**Owner:** Cursor · **Plan Prompt B:** unveraendert Sprints in `SPRINT_PLAN.md` / unten.

---

## Sprint 1 (Prompt B) — Stand

| ID | Status | Nachweis |
|----|--------|----------|
| P0-1 | **Done** | Policy: `BRANCH_AND_COMMIT_POLICY.md`; Commit: `54f3917b647ff65748cecf35c720b38d1ad61005` (`RUN_SPRINT1_2026-04-08.md`). |
| P0-2 | **Teil** | `pnpm check-types` grün (`RUN_SPRINT1_2026-04-08.md`); volles `pnpm test` / CI auf Remote noch auszuführen. |
| P0-3 | **Teil** | `rc:health` grün nach P0-0 (`RUN_P0-0_REDIS_READINESS.md`); wiederholbarer Lauf auf CI/Remote weiter dokumentieren. |
| P0-4 | **Teil** | Broken-interactions erweitert; grüner Lauf lokal nach Image-Rebuild / ein Dev-Server (siehe Evidence). |
| P2-3 | **Done** | `python tools/validate_env_profile.py --help` Exit 0 (Windows/cp1252). |
| P1-3 | **Teil** | Locale-Mirror: keine stillen Catches mehr (`best-effort-fetch.ts` + Tests). Weitere `.catch(()=>{})` per Grep in Sprint E. |

---

## P0 — Blocker / Integrität

| ID | Thema | DoD | Betroffene Bereiche |
|----|-------|-----|---------------------|
| P0-0 | **Redis ↔ Gateway stabil** | **Done** — `check_redis_url` Retry + höheres Timeout nur Gateway-/ready; Evidence `AUDIT_EVIDENCE/RUN_P0-0_REDIS_READINESS.md`; pytest `tests/unit/shared_py/test_check_redis_url_retries.py`. | `shared_py/observability/health.py`, `api-gateway`, `config/gateway_settings.py` |
| P0-1 | **Erster Git-Commit & Branch-Policy** | Repo hat `main`/`master` mit initialem Commit; `git status` clean für CI; Tag-Strategie dokumentiert. | ganzes Repo |
| P0-2 | **CI grün auf Commit** | Mindestens: `pnpm check-types`, `pnpm test` (turbo), Python-Selfcheck optional; dokumentiert in `AUDIT_EVIDENCE`. | `.github/`, `turbo.json` |
| P0-3 | **Stack-Smoke wiederholbar** | `docker compose ps` + **`pnpm rc:health` Exit 0** in Evidence (ohne Flake); Log-Auszug. | `docker-compose.yml`, `scripts/` |
| P0-4 | **E2E Release-Gate gegen echte URLs** | `pnpm e2e` mit dokumentiertem `E2E_BASE_URL` + Auth; Ergebnis JUnit/HTML angehängt. | `e2e/` |

---

## P1 — Ernsthaft (Live/Daten/Vertrauen)

| ID | Thema | DoD | Betroffene Bereiche |
|----|-------|-----|---------------------|
| P1-1 | **Vollständiger Link-Crawl Konsole** | `BROKEN_LINKS.md` gefüllt: alle internen `a[href]` unter `/console` → HTTP + Screenshot-Pfad. | `e2e/` neue Spec |
| P1-2 | **Button/Form-State-Matrix** | `BROKEN_BUTTONS.md`: kritische Aktionen (Self-Healing, Explain-Submit, Commerce) mit Zustandsdiagramm. | `apps/dashboard` |
| P1-3 | **Silent-error Elimination (Top 10)** | Grep-gestützte Liste `.catch(()=>{})` / leere catches; pro Fund Fix oder dokumentierte Ausnahme. | `apps/dashboard`, `tools/` |
| P1-4 | **Marktuniversum Lastprofil** | Dokumentierter Test mit N Symbolen (z. B. 500+): Pagination/Timeouts; Ergebnis in Report. | `market-universe`, Gateway, DB |
| P1-5 | **KI Eval-Gate in CI** | `pnpm llm:eval` oder `pytest tests/llm_eval` in Pipeline; Artefakt `artifacts/llm_eval/`. | `.github/`, `tests/llm_eval` |
| P1-6 | **Ribbon vs. Seiten-Lage konsistent** | Einheitliche Quelle oder erklärbarer Konflikt-Hinweis (Health-Zeitstempel). | `ConsoleExecutionModeRibbon`, `LiveDataSituationBar` |

---

## P2 — Verbesserung / UX / Perf

| ID | Thema | DoD |
|----|-------|-----|
| P2-1 | Paper/News/Strategies vollständige i18n | Keine hardcodierten UI-Strings laut `PAGE_COMPLETION_MATRIX` Restliste. |
| P2-2 | Ops-Cockpit „Above the fold“ | Ein Panel mit 5 KPIs für Einsteiger. |
| P2-3 | `validate_env_profile.py` UX | **Done** (Sprint 1): `--help` Windows/cp1252; Validator-Lauf siehe `RUN_2026-04-07.md`. |
| P2-4 | Audit-Dashboard | Ein Markdown-Index verlinkt alle `docs/audit/*` aus `README.md` (optional). |

---

## Plan für Prompt B (3–6 Sprints — Kurzfassung)

1. **Sprint A — Baseline:** P0-1–P0-4 (Git, CI, Stack-Smoke, E2E-Nachweis).  
2. **Sprint B — Transparenz:** P1-6 + Health-Fehlerpfade über alle Kernseiten.  
3. **Sprint C — Interaktion:** P1-1, P1-2 (Crawler + kritische Buttons).  
4. **Sprint D — KI:** P1-5 + Use-Case-Scorecards mit goldenen Prompts.  
5. **Sprint E — Härte:** P1-3, P1-4 (Silent errors + Universe-Skalierung).  
6. **Sprint F — Polish:** P2-* und Matrix-Schließung.
