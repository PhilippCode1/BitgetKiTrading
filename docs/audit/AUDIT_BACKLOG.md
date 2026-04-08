# AUDIT_BACKLOG — Priorisiert (Owner: Cursor / Team)

**Legende DoD:** Jede P0/P1-Story schließt mit **Testnachweis** (pytest/playwright/turbo) + **Doku-Update** in `docs/audit/AUDIT_EVIDENCE/`.

---

## Sprint 1 (Prompt B) — Stand

| ID | Status | Nachweis |
|----|--------|----------|
| P0-1 | **Teil** | Policy: `docs/audit/BRANCH_AND_COMMIT_POLICY.md`; **Commit:** nach `git commit` erledigt (Hash in nächstem RUN eintragen). |
| P0-2 | **Teil** | `pnpm check-types` grün (`RUN_SPRINT1_2026-04-08.md`); volles `pnpm test` / CI auf Remote noch auszuführen. |
| P0-3 | **Offen** | Stack-Smoke-Log in Follow-up `RUN_*.md`. |
| P0-4 | **Teil** | Neue Spec + JUnit-Reporter; grüner Lauf in **CI** `compose_healthcheck` + Playwright (siehe `.github/workflows/ci.yml`). |
| P2-3 | **Done** | `python tools/validate_env_profile.py --help` Exit 0 (Windows/cp1252). |
| P1-3 | **Teil** | Locale-Mirror: keine stillen Catches mehr (`best-effort-fetch.ts` + Tests). Weitere `.catch(()=>{})` per Grep in Sprint E. |

---

## P0 — Blocker / Integrität

| ID | Thema | DoD | Betroffene Bereiche |
|----|-------|-----|---------------------|
| P0-1 | **Erster Git-Commit & Branch-Policy** | Repo hat `main`/`master` mit initialem Commit; `git status` clean für CI; Tag-Strategie dokumentiert. | ganzes Repo |
| P0-2 | **CI grün auf Commit** | Mindestens: `pnpm check-types`, `pnpm test` (turbo), Python-Selfcheck optional; dokumentiert in `AUDIT_EVIDENCE`. | `.github/`, `turbo.json` |
| P0-3 | **Stack-Smoke wiederholbar** | `docker compose up` + `rc:health` oder `local:doctor` Exit 0; Log-Auszug in `RUN_*.md`. | `docker-compose.yml`, `scripts/` |
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
| P2-3 | `validate_env_profile.py` UX | `--help` funktioniert zuverlässig (Windows/PowerShell); Doku aktualisiert. |
| P2-4 | Audit-Dashboard | Ein Markdown-Index verlinkt alle `docs/audit/*` aus `README.md` (optional). |

---

## Plan für Prompt B (3–6 Sprints — Kurzfassung)

1. **Sprint A — Baseline:** P0-1–P0-4 (Git, CI, Stack-Smoke, E2E-Nachweis).  
2. **Sprint B — Transparenz:** P1-6 + Health-Fehlerpfade über alle Kernseiten.  
3. **Sprint C — Interaktion:** P1-1, P1-2 (Crawler + kritische Buttons).  
4. **Sprint D — KI:** P1-5 + Use-Case-Scorecards mit goldenen Prompts.  
5. **Sprint E — Härte:** P1-3, P1-4 (Silent errors + Universe-Skalierung).  
6. **Sprint F — Polish:** P2-* und Matrix-Schließung.
