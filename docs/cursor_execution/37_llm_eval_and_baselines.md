# 37 — LLM-Eval, Baseline und Modellwechsel

## Ziel

**Reproduzierbare Baseline** für die zentralen KI-Aufgaben (Operator Explain, Strategie-Signal-Explain inkl. Chart-Annotationen, Assist-Segmente), die Cursor und das Team bei **Regressionen** und **Modellwechseln** nutzen können. Die Suite läuft **ohne OpenAI** über den Fake-Provider (`LLM_USE_FAKE_PROVIDER=true` in `tests/llm_eval/conftest.py`).

## Artefakte und Pfade

| Artefakt                                          | Pfad                                                                                                       |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Case-Liste + Qualitätsdimensionen (Mensch-lesbar) | `shared/prompts/eval_baseline.json`                                                                        |
| Eval-Runner (CI / `pnpm llm:eval`)                | `tools/run_llm_eval.py`                                                                                    |
| Baseline-JSON-Validator                           | `tools/validate_eval_baseline.py`                                                                          |
| Pytest-Suite                                      | `tests/llm_eval/*.py`                                                                                      |
| Chart-Annotation-Sanitize (Unit)                  | `tests/llm_orchestrator/test_chart_annotation_sanitize.py`                                                 |
| Optional: JUnit + Zusammenfassung                 | `artifacts/llm_eval/junit.xml`, `artifacts/llm_eval/run_summary.json` (nicht versioniert außer `.gitkeep`) |

**Report erzeugen:** `pnpm llm:eval:report` bzw. `python tools/run_llm_eval.py --write-report`

## Metriken und Qualitätskriterien (Mapping)

Die folgenden **Dimensionen** sind in `eval_baseline.json` unter `quality_dimensions_de` beschrieben und durch Tests abgedeckt (Fake-Baseline):

| Dimension                        | Was geprüft wird                                                                                 | Wo                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| **Schema-Treue**                 | HTTP 200, `ok`, strukturiertes `result` gemäß Orchestrator-Pipeline                              | `test_eval_regression.py`, Assist-/Operator-/Strategie-Tests |
| **Pflichtfelder**                | `execution_authority == "none"`, Assist `assist_role_echo`, `trade_separation_note_de` (Billing) | `test_eval_*`, `test_eval_assist_cases.py`                   |
| **Sprachliche Klarheit / Länge** | Mindestlänge deutscher Pflichttexte; Fake-Antworten enthalten `TEST-PROVIDER`                    | `test_eval_operator_strategy_quality.py`, Assist-Tests       |
| **Annotation-Sanity**            | `chart_annotations.schema_version == "1.0"`, `chart_notes_de` nicht leer                         | `test_eval_chart_annotations.py`                             |
| **Gefährliche Aussagen**         | Imperative, Gewinngarantie, Secrets, interne Header-Hinweise                                     | `test_guardrails.py`                                         |
| **Leere Antworten**              | indirekt: Mindestlänge + Pflichtstrings                                                          | Operator/Strategie/Assist-Tests                              |
| **Degradierter Provider**        | Fake-Modus: `/health` → `fake_mode: true`                                                        | `test_eval_provider_fake.py`                                 |
| **Chart ms-Korrektur**           | Sanitizer verwirft falsche Schema-Versionen, korrigiert ms→s                                     | `tests/llm_orchestrator/test_chart_annotation_sanitize.py`   |

## Eval-Set: Fälle (Baseline-Cases)

Die Spalte **Case-ID** entspricht `eval_baseline.json` → `cases[].id` (10 Einträge, Stand Baseline `llm-eval-baseline-2026.04.05-p37`).

| Case-ID                            | Kategorie          | Abdeckung                     |
| ---------------------------------- | ------------------ | ----------------------------- |
| `operator_explain_smoke`           | operator           | Operator Explain + Provenance |
| `strategy_signal_explain_smoke`    | strategy           | Strategie-/Signal-Explain     |
| `chart_annotations_smoke`          | chart_intelligence | `chart_annotations` + Notizen |
| `admin_operations_assist_smoke`    | admin_assist       | Assist Admin                  |
| `customer_onboarding_assist_smoke` | customer_help      | Assist Onboarding             |
| `support_billing_assist_smoke`     | billing            | Assist Billing                |
| `trial_contract_context_smoke`     | trial_contract     | Trial-Kontext                 |
| `eval_fake_provider_health`        | provider           | Health Fake-Modus             |
| `governance_summary_contract`      | governance         | Governance-GET                |
| `guardrails_policy`                | guardrails         | Output-Guardrails (Unit)      |

## KI-Ausgabeflächen (Produkt ↔ Eval)

| Produktfläche                              | Backend-Pfad (Orchestrator)                   | Eval-Abdeckung                                                             |
| ------------------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------- |
| Health — Operator Explain                  | `POST /llm/analyst/operator_explain`          | Operator-Smoke + Qualität + Guardrails                                     |
| Signaldetail — Strategie-Erklärung         | `POST /llm/analyst/strategy_signal_explain`   | Strategie-Smoke + Chart-Case                                               |
| Assist (Admin/Strategy/Onboarding/Billing) | `POST /llm/assist/turn`                       | `test_eval_assist_cases.py`                                                |
| Dashboard Chart-Layer                      | Antwortfeld `chart_annotations` + UI-Sanitize | Eval: Schema/Notizen; UI: `apps/dashboard` `llm-chart-annotations.test.ts` |

## Befehle (Nachweise)

```text
# Gesamte Eval-Suite (wie CI)
python tools/run_llm_eval.py

# Mit Report-Dateien
pnpm llm:eval:report

python tools/validate_eval_baseline.py

# Orchestrator-Chart-Sanitize (zusätzlich)
pytest tests/llm_orchestrator/test_chart_annotation_sanitize.py -q --tb=short

# Dashboard (KI-bezogene Unit-Tests)
cd apps/dashboard && pnpm test -- src/lib/chart/__tests__/llm-chart-annotations.test.ts src/lib/__tests__/llm-response-layout.test.ts --runInBand
```

## Modellwechsel: empfohlene Prüfreihenfolge

1. **Lokal/CI:** `pnpm llm:eval` grün halten (Fake bleibt Regression-Grundlage).
2. **Staging mit echtem Modell:** `LLM_USE_FAKE_PROVIDER=false`, gültiger `OPENAI_API_KEY` am **llm-orchestrator**; manuell dieselben Endpunkte mit realistischen Prompts ansprechen.
3. **Qualität:** Stichproben auf Deutsch (Klarheit, keine imperativen Trade-Aufforderungen), Stichprobe `chart_annotations` im UI mit sichtbaren Kerzen.
4. **Baseline bump:** Bei neuer Case-Liste oder geändertem Release-Gate `baseline_id` in `eval_baseline.json` erhöhen und in PR beschreiben.
5. **Optional:** `pnpm llm:eval:report` ausführen und `run_summary.json` + `junit.xml` der Release-Evidence beilegen.

## Regression vs. Baseline

- **Baseline:** `eval_baseline.json` + grüne `tests/llm_eval` bei Fake-Provider.
- **Regression:** Jedes rote `pytest tests/llm_eval` blockt das Release-Gate (siehe `tools/production_selfcheck.py`, `services/llm-orchestrator` Governance-Hinweis).

## Offene Punkte

- **[FUTURE]** Echte-Modell-Goldenfiles (gegen Kosten/Lock-in) nur auf Branch oder nächtlich.
- **[FUTURE]** Automatische Auswertung von `junit.xml` in einem Dashboard-Job.
