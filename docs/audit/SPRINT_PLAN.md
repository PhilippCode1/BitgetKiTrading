# SPRINT_PLAN — Prompt B (bitget-btc-ai)

**Stand:** 2026-04-08 · **Quelle:** `AUDIT_BACKLOG.md`, `AUDIT_SCORECARD.md`, `AUDIT_REPORT.md`  
**Regeln:** Nach jedem Sprint `AUDIT_SCORECARD.md`, `AUDIT_BACKLOG.md`, `AUDIT_EVIDENCE/RUN_*.md` aktualisieren; kleine, testbare Inkremente; kein Big-Bang.

---

## Sprint 1 — UX-Blocker, Broken Links/Buttons, E2E-Sicherheitsnetz

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | P0-1 sauberer Git-Stand (Commits pro Inkrement); P0-2 `pnpm check-types` + Dashboard-Tests; P0-3 Stack-Smoke **oder** dokumentiertes „blocked“ mit Ursache; P0-4 E2E erweitern: Sidebar-Crawl **plus** feste Liste **kritischer** `/console/*`-Pfade; **mindestens eine** sichere Button-Interaktion pro Kernoberfläche (Terminal Reload, Signale-Filter-Link, aufklappbare `<details>` ohne Destruktivität); keine 404/500/`pageerror`/harte Alert-Banner auf diesen Pfaden. |
| **DoD** | `broken-interactions.spec.ts` grün in CI; `BROKEN_LINKS.md` / `BROKEN_BUTTONS.md` entweder leer **oder** Tabelle **blocked** mit Grund + Fix-Pfad; P0-3: `RUN_*_STACK.md` **oder** „blocked: kein Docker lokal“. |
| **Tests/Evidence** | `pnpm check-types`; `pnpm --filter @bitget-btc-ai/dashboard test`; `pnpm e2e -- e2e/tests/broken-interactions.spec.ts`; JUnit wie in `e2e/playwright.config.ts`. |
| **Risiko/Backout** | E2E zu strikt: Pfade oder Assertions lockern; Backout = Git-Revert der Spec. |

---

## Sprint 2 — Echte Datenpfade & Marktuniversum sichtbar

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | LIVE/SHADOW/PAPER, Last-Update, Staleness, Datenqualität auf Terminal, Signale, Marktuniversum (Health-Lineage bereits vorhanden — ausbauen wo Lücken); dynamische Symbol-/Produktlisten aus Gateway/Catalog; Pagination/Virtualisierung für große Mengen; bei fehlenden Streams: konkreter Text (was fehlt, Self-Healing-Hinweis). |
| **DoD** | BTCUSDT/ETHUSDT: Chart aktualisiert, Live-State, Market-Stream-Status, Broker-Reconcile sichtbar; kein „mystery emptiness“; Evidence-Screenshots oder Playwright-Assertions. |
| **Tests/Evidence** | `release-gate.spec.ts` + API-Smoke gegen Gateway; `RUN_SPRINT2_*.md`. |
| **Risiko/Backout** | Gateway down: nur degraded UI, keine weißen Screens; Backout = Feature-Flag pro Panel. |

---

## Sprint 3 — KI-Qualität (10/10): Evals, Guardrails, Versionierung, UI-Erklärungen

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Prompts nur unter `shared/prompts` + Manifest/Baseline; Golden-Sets in `tests/llm_eval`; CI-Gate bei Regressions (`validate_eval_baseline` / `pnpm llm:eval`); Timeouts/Retry/Fallback im Orchestrator/BFF; UI-Copy: Was tut KI, warum, was bei Fehler. |
| **DoD** | Pro Use-Case (Operator Explain, Strategy/Signal Explain, Safety, Assist, Chart-Annotations): Scorecard ≥10 **mit** Eval-Nachweis; CI rot bei Baseline-Bruch; Artefakt `artifacts/llm_eval/` im Release-Prozess. |
| **Tests/Evidence** | `pytest tests/llm_eval`; `pnpm llm:eval:report`; Workflow-Logs. |
| **Risiko/Backout** | Kosten: Fake-Provider in CI; Live-Eval nur Release/manuell. |

---

## Sprint 4 — Observability, Self-Healing, Diagnosezentrum

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Zentrale Diagnose: Services Health/Ready, Streams, DB/Redis, Broker-Reconcile, Eventbus; pro Problem: Ursache, Impact, Fix-Aktion, letzte Sichtung; Self-Healing: **reale** API-Aktionen (Reconnect, Cache-Refresh, Resubscribe) **oder** explizite Grenze „nicht automatisch“. |
| **DoD** | Keine dekorativen Repair-Buttons; jede Aktion: Erfolg/Fehler sichtbar; Logs korrelierbar (`supportReference` o. ä.). |
| **Tests/Evidence** | Integration gegen Mock-Gateway; E2E Diagnose-/Self-Healing-Smoke; `RUN_SPRINT4_*.md`. |
| **Risiko/Backout** | Mutationen hinter Feature-Flags; Backout = Flag aus. |

---

## Sprint 5 — Performance, Skalierung, Polish

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Marktuniversum Lastprofil (z. B. 500+ Symbole) dokumentiert + Timeout/Pagination-Verhalten; i18n-Reste (`PAGE_COMPLETION_MATRIX`); Ops „Above the fold“ KPIs; P1-6 Ribbon vs. `LiveDataSituationBar` konsolidieren oder Konflikt-Hinweis; optionale Bundle/Lighthouse-Checks. |
| **DoD** | P1-4 Dokument mit Messergebnis; Matrix-Abgleich; Regression-E2E grün. |
| **Tests/Evidence** | Last-Skript oder Playwright mit vielen Symbolen; `RUN_SPRINT5_*.md`. |
| **Risiko/Backout** | Virtualisierung: UX-Regression — Toggle oder schrittweise Ausrollung. |

---

## Reihenfolge (Nutzen zuerst)

1. **Sprint 1** — Nichts Tot-Klickbares auf Kernpfaden; E2E-Netz.  
2. **Sprint 2** — Datenherkunft und Kernsymbole glasklar.  
3. **Sprint 3** — KI messbar und gatebar.  
4. **Sprint 4** — Betrieb und Heilung.  
5. **Sprint 5** — Skalierung und Feinschliff.

---

## Historische Umsetzung (Kurz)

| Sprint | Erreicht (Auszug) |
|--------|-------------------|
| Sprint 1 (früher) | `broken-interactions` Sidebar, Locale-Catch-Fix, Policy-Doku |
| Sprint 2 | Marktuniversum-Lineage, Pagination, `PlatformExecutionStreamsGrid` Terminal/Signale, Release-Gate-`testid`s |
