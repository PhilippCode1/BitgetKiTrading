# Release-Readiness (KI-Strecke & nächster Schritt)

Kurzfassung für **Betrieb und nächsten produktiven Schritt** rund um die **zwei** echten Dashboard-KI-Pfade (**Operator Explain** auf Health, **Strategie-Signal-Erklaerung** auf Signaldetail). Für den **gesamten** Markt-/Trading-Stack gelten zusätzlich `docs/LAUNCH_DOSSIER.md`, `docs/Deploy.md`, `README.md`.

---

## Setup (lokal oder Compose)

1. **Stack:** Gateway, LLM-Orchestrator, Redis (Orchestrator), Postgres wo nötig — z. B. `pnpm stack:local`, `docker compose`, oder Skripte aus `README.md`.
2. **Gateway-ENV:** `INTERNAL_API_KEY` (identisch zum Orchestrator), `LLM_ORCH_BASE_URL` **oder** `HEALTH_URL_LLM_ORCHESTRATOR` (Basis-URL wird ggf. abgeleitet). Siehe `config/gateway_settings.py` (`llm_orchestrator_http_base`).
3. **Orchestrator-ENV:** `OPENAI_API_KEY` für echte Modellantworten; `LLM_USE_FAKE_PROVIDER=true` nur für Tests/CI ohne Live-OpenAI.
4. **Dashboard (.env.local):** `API_GATEWAY_URL` (oder Projekt-Fallback), **`DASHBOARD_GATEWAY_AUTHORIZATION`** = `Bearer …` mit Rolle `gateway:read` — z. B. `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`, danach **Next neu starten**.
5. **UI:** Konsole → **Health** → Panel **Operator assistant**; optional Signaldetail → Panel **KI: Strategie- und Signalerklaerung**.

Details und Klickpfad: `ai-architecture.md` (Abschnitt „Lokaler End-to-End-Test“).

---

## Teststatus (relevante Kommandos)

| Bereich                                   | Befehl (Repo-Root bzw. Dashboard)                                                                                                                                                                     |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CI-Gates (Pflicht vor Merge auf main)** | Siehe **`docs/ci_release_gates.md`** — Jobs `python`, `dashboard`, `compose_healthcheck` in `.github/workflows/ci.yml` (Branch-Protection im Remote einrichten).                                      |
| Gateway LLM-Route (gemockt)               | `python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q`                                                                                                                              |
| LLM-Orchestrator (Fake, ohne Compose)     | `pytest tests/llm_orchestrator/test_structured_fake_provider.py::test_analyst_hypotheses_and_operator_explain -q` (deckt auch Strategie-Signal-Erklaerung ab)                                         |
| Strategie-Signal E2E (Skript)             | `python scripts/verify_ai_strategy_signal_explain.py --env-file .env.local --mode orchestrator`                                                                                                       |
| Stack + KI nach Compose (wie CI)          | Nach grünem `healthcheck.sh`: `python scripts/rc_health_runner.py .env.local` dann `python scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator`                           |
| **Release-Gate (ein Kommando)**           | `pnpm release:gate` — Smokes + RC-Health + KI + `dashboard_page_probe` (ohne Browser). Mit laufendem Dashboard: `pnpm release:gate:full` inkl. Playwright.                                            |
| **UI-Freigabeliste (manuell)**            | `docs/FREIGABELISTE_UI.md` — Kernreisen, Mobile, Staging-Hinweis                                                                                                                                      |
| Playwright E2E (wie CI)                   | `pnpm e2e:install` dann `pnpm e2e` (Default `E2E_BASE_URL=http://127.0.0.1:3000`)                                                                                                                     |
| Dashboard Fehler-/Payload-Helfer          | `cd apps/dashboard && pnpm test -- src/lib/__tests__/operator-explain-errors.test.ts src/lib/__tests__/strategy-signal-explain-errors.test.ts src/lib/__tests__/api-error-detail.test.ts --runInBand` |
| Dashboard Typecheck                       | `cd apps/dashboard && pnpm exec tsc --noEmit`                                                                                                                                                         |

**Manuell:** eine Frage absenden, Fehlerfälle (Gateway aus, falsches JWT, fehlender OpenAI-Key) prüfen — erwartet werden **klare** UI-Meldungen, kein stilles Scheitern (`qa-report.md`).

**Release / Rollback:** Kurzfassung in **`docs/ci_release_gates.md`** (Abschnitte Freigabe und Rollback).

---

## Offene / bekannte Punkte

- Kein persistenter Chat; weitere LLM-Endpunkte im Dashboard nur mit neuer Gateway+BFF+Schema-Implementierung.
- **Compose-Job** (`compose_healthcheck`): nach HTTP-Smokes und KI-Orchestrator-Check läuft **Playwright** (`e2e/tests/release-gate.spec.ts`) gegen das Dashboard — Startseite, Konsole, Terminal/Chart, BFF Operator-Explain, Broker, Kernnavigation.
- Produktions-Freigabe des **gesamten** Systems unabhängig von dieser KI-Datei — siehe Launch-Dossier.

---

## Nächster produktiver Schritt (empfohlen)

1. In der **Zielumgebung** (Staging) dieselben ENV wie oben setzen und **einen** erfolgreichen Operator-Explain-Call verifizieren (Logs Gateway + Orchestrator).
2. **`LLM_USE_FAKE_PROVIDER`** in Staging/Prod **aus**; Keys nur im Secret Store.
3. Optional: **Alerting**, wenn Orchestrator-Health rot oder LLM-Fehlerquote steigt.
4. Erst danach: weitere Features skalieren (siehe `PRODUCT_STATUS.md`, Abschnitt 3).

---

## Querverweise

- Architektur KI: `ai-architecture.md`
- Lieferstatus / Blocker: `PRODUCT_STATUS.md`
- UX-QA Operator-Explain: `qa-report.md`
