# SPRINT_PLAN — Prompt B (bitget-btc-ai)

**Erstellt:** 2026-04-08 (Iteration 1)  
**Quelle:** `AUDIT_BACKLOG.md`, `AUDIT_SCORECARD.md`, `AUDIT_REPORT.md`  
**Regeln:** Nach jedem Sprint Scorecard/Backlog/Evidence aktualisieren; kleine, testbare Schritte.

---

## Sprint 1 — UX-Blocker + Broken Links/Buttons eliminieren

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | P0-1 Branch/Commit-Policy-Doku; P0-2 lokaler Nachweis `check-types` + Dashboard-Tests; `validate_env_profile.py --help` Windows/cp1252-sicher; stille `.catch(()=>{})` bei Locale-Mirror durch sichtbare `console.warn`-Protokollierung ersetzen; E2E **Broken-Interactions**: alle sichtbaren Sidebar-Links unter `/console` traversieren + Kern-öffentliche Routen; keine `pageerror`; HTTP 2xx; Shell sichtbar. |
| **DoD** | `python tools/validate_env_profile.py --help` Exit 0 unter Windows; neue Spec `e2e/tests/broken-interactions.spec.ts` grün in CI (Compose + Playwright); `BROKEN_LINKS.md` / `BROKEN_BUTTONS.md` verweisen auf E2E-Abdeckung + Restrisiko; `AUDIT_BACKLOG` P0-2/4 teilweise erledigt markiert. |
| **Tests/Evidence** | `pnpm check-types`; `pnpm --dir apps/dashboard run test`; CI: bestehender Job `compose_healthcheck` + Playwright; optional lokal `pnpm e2e`; JUnit: `e2e/test-results/junit.xml`. |
| **Risiko/Backout** | E2E-Liste zu strikt: Route aus Liste nehmen oder UI fixen; Backout = Spec revert. |

---

## Sprint 2 — Echte Datenpfade & Marktuniversum sichtbar

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | LIVE/SHADOW/PAPER + `last update` + Staleness auf Chart, Terminal, Signal-Center, Market-Universe; Broker-Reconcile-Status; fehlende Streams mit Ursache + Self-Healing-Hinweis (keine leeren Zustände ohne Text); dynamische Symbolliste aus Gateway/Catalog-API wo vorhanden; Pagination/Virtualisierung für große Listen. |
| **DoD** | Für BTCUSDT/ETHUSDT: sichtbarer Live-State, Stream-Status, Reconcile; keine „mystery emptiness“; Evidenz-Screenshots in `AUDIT_EVIDENCE/`. |
| **Tests** | Erweiterte Playwright-Szenarien mit Mock oder Stack; API-Smoke gegen Gateway `/v1/...` wo dokumentiert. |
| **Risiko/Backout** | Gateway down: UI muss degraded anzeigen (bereits teils vorhanden) — keine Regression zu harten Crashes. |

---

## Sprint 3 — KI 10/10 (Evals, Guardrails, Versionierung)

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Prompt-Artefakte nur unter `shared/prompts` + Manifest-Version; Golden-Datasets pro Use-Case (`tests/llm_eval`); `validate_eval_baseline.py` + CI-Gate bei Score-Regression; Timeouts/Retry im Orchestrator/BFF dokumentiert und getestet; UI-Copy: was KI tut, Fehler, Fallback. |
| **DoD** | Pro Use-Case (Operator Explain, Strategy Explain, Safety, Assist): Scorecard-Eintrag ≥10 mit Eval-Nachweis; CI rot bei Baseline-Bruch. |
| **Tests** | `pnpm llm:eval` / `pytest tests/llm_eval`; Artifact Upload in CI. |
| **Risiko/Backout** | Externe API-Kosten: Fake-Provider in CI, Live-Eval nur manuell/release. |

---

## Sprint 4 — Observability + Self-Healing + Diagnosezentrum

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Diagnose-UI: Matrix aller Services (Health/Ready), Redis/Postgres, Streams, Broker, Eventbus; Fehler mit Ursache/Impact/Fix/Letzte Sichtung; Self-Healing: reale API-Actions (Reconnect, Cache-Refresh) oder explizite Grenze „nicht automatisch“. |
| **DoD** | Keine rein dekorative Repair-Buttons; jede Aktion: Erfolg/Fehler sichtbar; Logs korrelierbar. |
| **Tests** | Integrationstests gegen Mock-Gateway; E2E Diagnose-Seite smoke. |
| **Risiko/Backout** | Zu breite Mutationen: Feature-Flags pro Aktion. |

---

## Sprint 5 — Performance, Skalierung, Polish

| Aspekt | Inhalt |
|--------|--------|
| **Scope** | Marktuniversum 500+ Symbole Profil; i18n-Rest aus Matrix; Ops „Above the fold“ KPIs; Audit-Index in README; Ribbon vs. Seitenlage konsolidieren (P1-6). |
| **DoD** | `PAGE_COMPLETION_MATRIX` geschlossen wo versprochen; Lighthouse/Bundle-Check optional. |
| **Tests** | Lasttest-Skript + Dokumentation; Regression E2E. |
| **Risiko/Backout** | Virtualisierung kann UX ändern — Feature-Toggle. |

---

## Reihenfolge (Nutzen zuerst)

1. Sprint 1 — Vertrauen: nichts Tot-Klickbares auf Kernpfaden.  
2. Sprint 2 — Daten echt sichtbar.  
3. Sprint 3 — KI messbar.  
4. Sprint 4 — Betrieb.  
5. Sprint 5 — Skalierung & Feinschliff.
