# 38 — Sicherheits-KI: Architektur, Grenzen, Nachweise

## Ziel

Eine **klar begrenzte Systemfunktion** („Sicherheits-Diagnose“), die **Health**, **Alerts**, **Outbox**, **Fehler beim Laden** und optional bearbeitbaren JSON-Kontext **zusammenführt**, um **Ursachen**, **Services**, **Repo-Pfade**, **Handlungspläne** und **textuelle Kommandovorschläge** zu liefern — **ohne** stillschweigende Live-Aktionen und **ohne** automatische Änderung geld- oder broker-sensitiver Einstellungen.

## Architektur (Datenfluss)

1. **Konsole Health (SSR):** `buildSafetyDiagnosticContext` erzeugt ein **redigiertes** JSON (`apps/dashboard/src/lib/safety-diagnosis-context.ts`) aus `GET /v1/system/health`, `GET /v1/monitor/alerts/open`, `GET /v1/alerts/outbox/recent` und `loadError`.
2. **Client:** `SafetyDiagnosisPanel` zeigt den Kontext als editierbares JSON + Diagnosefrage; Submit → BFF.
3. **BFF:** `POST /api/dashboard/llm/safety-incident-diagnose` — erneute **Redaction** sensibler Schlüssel, Größenlimit wie Operator-Explain-Kontext.
4. **Gateway:** `POST /v1/llm/operator/safety-incident-diagnosis` — `require_sensitive_auth`, Audit-Action `llm_operator_safety_incident_diagnosis`.
5. **Orchestrator:** `POST /llm/analyst/safety_incident_diagnosis` — Structured Output gegen `safety_incident_diagnosis.schema.json`, Task `safety_incident_diagnosis`, Retrieval-Tags wie Runbook/Operator.

## Schema & Policy

| Artefakt    | Pfad                                                                                                             |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| JSON-Schema | `shared/contracts/schemas/safety_incident_diagnosis.schema.json`                                                 |
| Prompt-Task | `shared/prompts/tasks/safety_incident_diagnosis.instruction_de.txt`                                              |
| Manifest    | `shared/prompts/prompt_manifest.json` (`safety_incident_diagnosis`, `manifest_version` 2026.04.05-p38-safety-ai) |

**Pflicht:** `execution_authority` ist Konstante **`none`**. Felder `proposed_commands_de` sind **nur Freitext-Vorschläge** (Schema-Beschreibung + UI-Warnbanner).

**Guardrails:** Task in `output_guardrails._FULL_TASKS` — gleiche Heuristiken wie andere Operator-Tasks (keine Imperative, keine Leaks).

## UI & Logs

| Komponente          | Pfad                                                                          |
| ------------------- | ----------------------------------------------------------------------------- |
| Panel + Formular    | `apps/dashboard/src/components/panels/SafetyDiagnosisPanel.tsx`               |
| Ergebnisdarstellung | `apps/dashboard/src/components/panels/SafetyDiagnosisResultView.tsx`          |
| Health-Seite        | `apps/dashboard/src/app/(operator)/console/health/page.tsx`                   |
| Styles              | `apps/dashboard/src/app/globals.css` (`.safety-diag-*`)                       |
| i18n                | `apps/dashboard/src/messages/de.json`, `en.json` (`pages.health.safetyDiag*`) |

**Logs / Korrelation:** Wie bei Operator Explain — `X-Request-ID` / `X-Correlation-ID` durch BFF und Gateway; Gateway-Audit-Zeile mit Kontext-Key-Count und Fragenlänge.

## Kontextquellen (Ist)

| Quelle                  | Im Bundle                                                                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| System-Health (Auszug)  | `system_health` (Aggregate, Readiness, DB, Freshness, Services, Ops, Warnings, …)                                                                    |
| Offene Monitor-Alerts   | `monitor_open_alerts` (Titel, Meldung, Details redigiert)                                                                                            |
| Alert-Outbox (kürzlich) | `alert_outbox_recent` (Payload redigiert)                                                                                                            |
| Lade-Fehler der Seite   | `dashboard_load_error`                                                                                                                               |
| **data_lineage**        | Nur **Hinweistext** im Bundle — vollständige Lineage liegt auf Terminal/Shadow-Live; bewusst nicht doppelt geladen, um Health-SSR schlank zu halten. |

## Sicherheitsgrenzen (verbindlich)

- Kein Endpunkt **schreibt** Health, Alerts, Broker, Orders oder Secrets zurück.
- BFF und Builder **entfernen** typische Secret-Keys (`password`, `token`, `api_key`, …) — ersetzt durch `[REMOVED]`; **kein Ersatz** für vollständiges Secret-Scanning durch Operatoren.
- **Kommandovorschläge:** UI warnt explizit vor automatischer Ausführung; Produkttexte betonen manuelle Prüfung und Runbooks.

## Technische Nachweise (Diagnose-Schnittstellen)

| Schnittstelle | Methode / Pfad                                     |
| ------------- | -------------------------------------------------- |
| Orchestrator  | `POST /llm/analyst/safety_incident_diagnosis`      |
| Gateway       | `POST /v1/llm/operator/safety-incident-diagnosis`  |
| Dashboard BFF | `POST /api/dashboard/llm/safety-incident-diagnose` |

## Tests

| Suite                    | Pfad / Befehl                                                           |
| ------------------------ | ----------------------------------------------------------------------- |
| Eval / Regression (Fake) | `tests/llm_eval/test_eval_safety_diagnosis.py`                          |
| Baseline-Case            | `shared/prompts/eval_baseline.json` → `safety_incident_diagnosis_smoke` |
| Kontext-Redaction        | `apps/dashboard/src/lib/__tests__/safety-diagnosis-context.test.ts`     |

```text
pytest tests/llm_eval/test_eval_safety_diagnosis.py -q --tb=short
cd apps/dashboard && pnpm test -- src/lib/__tests__/safety-diagnosis-context.test.ts --runInBand
pnpm check-types
```

## Modellwechsel / Betrieb

- Regressions-Grundlage: `pnpm llm:eval` inkl. neuem Eval-Case (`docs/cursor_execution/37_llm_eval_and_baselines.md`).
- Staging: gleiche Route mit `LLM_USE_FAKE_PROVIDER=false` — Stichproben auf **keine** imperativen Formulierungen in `incident_summary_de` / `proposed_commands_de`.

## Offene Punkte

- **[FUTURE]** Optionales Einbinden von `data_lineage` aus einem zweiten clientseitigen Fetch (Terminal-Symbol/TF) mit explizitem Opt-in.
- **[FUTURE]** Dedizierte Fehlercodes-Matrix aus Gateway in den Kontext (derzeit über Health/Warnings abgedeckt).
