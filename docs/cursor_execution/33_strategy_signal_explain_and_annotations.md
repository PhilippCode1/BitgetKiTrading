# 33 — Strategy-Signal-Explain und KI-Chart-Annotationen

## Ziel

Die Strecke **Strategie-Signal-Erklärung** vom Signaldetail über BFF, Gateway und Orchestrator bis zur Darstellung von `chart_annotations` im **ProductCandleChart** soll nachvollziehbar, validiert und ehrlich kommunizieren: keine behauptete dauerhafte Perfektion der Linien, sondern technische Transparenz (Sanitizer, Grenzen, Hinweise).

Referenzen: `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md`, `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md`.

## End-to-End-Kette

1. **UI:** `console/signals/[id]` → `StrategySignalExplainPanel` → `POST /api/dashboard/llm/strategy-signal-explain` mit `signal_context_json` (+ optional `focus_question_de`).
2. **BFF:** `apps/dashboard/src/app/api/dashboard/llm/strategy-signal-explain/route.ts` — Gateway-Auth, Größenlimit Snapshot (413 `SIGNAL_CONTEXT_TOO_LARGE`), Trace-Header.
3. **Gateway:** `POST /v1/llm/operator/strategy-signal-explain` — `routes_llm_operator.py`, Audit `llm_operator_strategy_signal_explain` (Key-Metadaten, kein Payload).
4. **Orchestrator:** `POST /llm/analyst/strategy_signal_explain` — Structured Output per `strategy_signal_explain.schema.json`, Guardrails, **Nachbearbeitung** `chart_annotations` (s. u.).
5. **Chart:** `StrategySignalExplainPanel` setzt rohe `chart_annotations` im Context (`signal-detail-llm-chart-context.tsx`) → `SignalDetailMarketChartBlock` → `ConsoleLiveMarketChartSection` → `ProductCandleChart` ruft `sanitizeLlmChartAnnotations` auf sichtbaren Kerzen auf.

## Sanitizer und Guardrails

### Dashboard (`sanitizeLlmChartAnnotations` / `sanitizeLlmChartAnnotationsDetailed`)

- Datei: `apps/dashboard/src/lib/chart/llm-chart-annotations.ts`
- **Unix-Zeiten:** Werte `> 1e11` werden als Millisekunden interpretiert und auf Sekunden reduziert (wie `time_s` der Kerzen). Meta-Feld `timestampsCorrectedFromMs` zählt Korrekturen.
- **Preise/Geometrie:** Nur innerhalb eines strikten Bandes um Min/Max der **sichtbaren** Kerzen; sonst verworfen (kein Throw).
- **Falsche `schema_version`:** Geometrie verworfen, **Notizen** (`chart_notes_de`) bleiben erhalten.
- **Meta** für UI: `geometryCandidatesTotal`, `geometryKeptTotal`, `wrongSchemaVersion`, `skippedGeometryNoStats`.

### Orchestrator (`sanitize_strategy_chart_annotations`)

- Datei: `services/llm-orchestrator/src/llm_orchestrator/chart_annotation_sanitize.py`
- Nach erfolgreicher Schema-Validierung in `run_strategy_signal_explain`: ms→s auf bekannten Zeitfeldern, Array-Längen auf Schema-`maxItems` begrenzt.
- Optional in `provenance`: `chart_annotation_unix_ms_corrected` (Anzahl), wenn Korrekturen stattfanden.

### Prompt

- `shared/prompts/tasks/strategy_signal_explain.instruction_de.txt` — verlangt **Sekunden**, keine ms; Hinweis auf Validierung/keine Perfektionsgarantie für Overlays.

## Produkt-Transparenz (UI-Texte)

- `pages.signalsDetail.aiStrategyChartHint` — Verbindung Antwort ↔ Chart, begrenzte Overlays.
- `ui.chart.llmLayerLead` / `llmLayerFootnote` / `llmLayerMsNormalized` / `llmLayerGeometryFiltered` — Kontext-Chart-Legende unter dem Kerzenchart (nur wenn KI-Layer aktiv und Rohdaten gesetzt).

## Beispiel-Payload (Fixture)

Datei: `tests/fixtures/chart_annotations/strategy_signal_chart_annotations_ms.json`

Enthält `time_markers[0].time_unix_s: 1700000000000` (ms) — nach Orchestrator-Sanitizer: `1700000000000 / 1000 = 1700000000` (s).

Minimalauszug:

```json
{
  "chart_annotations": {
    "schema_version": "1.0",
    "horizontal_lines": [{ "price": 98500.5, "label": "Beispiel-Level" }],
    "time_markers": [
      { "time_unix_s": 1700000000000, "label": "ms statt s", "shape": "circle" }
    ],
    "chart_notes_de": [{ "text": "Demo-Notiz fuer Nachweisdokumentation." }]
  }
}
```

## Visueller / funktionaler Nachweis (ohne Screenshot-Pflicht)

**Ablauf (manuell):**

1. Stack mit Gateway, Orchestrator, Dashboard; `LLM_USE_FAKE_PROVIDER=true` am Orchestrator für deterministische Antwort inkl. `chart_annotations`.
2. Signaldetail öffnen, „Erklärung anfordern“.
3. Unter dem Chart: Checkbox „KI-Zeichnung“, Legendentexte (Footnote, ggf. ms-Hinweis).
4. Erwartung: violette Overlays (Fake liefert Struktur), Strategie-Overlay (farbig getrennt) bleibt eigenständig.

**ASCII-Skizze der Schichten:**

```text
┌─────────────────────────────────────┐
│ Kerzen (tsdb / live state)          │
│  · Strategie-Preislinien (Gateway)  │
│  · KI-Layer (llm, violett, gefiltert)│
└─────────────────────────────────────┘
```

## Automatisierte Tests (ausgeführt)

```text
# Repo-Root
python -m pytest tests/llm_orchestrator/test_chart_annotation_sanitize.py ^
  tests/llm_orchestrator/test_structured_fake_provider.py ^
  tests/unit/api_gateway/test_routes_llm_operator.py -q --tb=short

python -m pytest tests/llm_eval/test_eval_regression.py -q --tb=short

# Dashboard
cd apps/dashboard
pnpm test -- src/lib/chart/__tests__/llm-chart-annotations.test.ts ^
  src/lib/__tests__/strategy-signal-explain-errors.test.ts --runInBand
```

**Ergebnis (lokaler Lauf dieser Session):** alle genannten Suiten grün (14 + 3 + 5 bzw. 15 Jest-Tests in den zwei Dateien).

## E2E-Skript

```text
python scripts/verify_ai_strategy_signal_explain.py --env-file .env.local --mode orchestrator
python scripts/verify_ai_strategy_signal_explain.py --env-file .env.local --mode gateway
```

Bei nicht erreichbarem Dienst: `FAIL transport: …` ohne Traceback (wie beim Operator-Skript).

## Betroffene / neue Dateien (Überblick)

| Komponente            | Pfad                                                                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Sanitizer + Meta      | `apps/dashboard/src/lib/chart/llm-chart-annotations.ts`                                                                                  |
| Sanitizer-Tests       | `apps/dashboard/src/lib/chart/__tests__/llm-chart-annotations.test.ts`                                                                   |
| Chart-Section UI      | `apps/dashboard/src/components/console/ConsoleLiveMarketChartSection.tsx`                                                                |
| Strategie-Panel       | `apps/dashboard/src/components/panels/StrategySignalExplainPanel.tsx`                                                                    |
| i18n                  | `apps/dashboard/src/messages/de.json`, `en.json`                                                                                         |
| Orchestrator-Sanitize | `services/llm-orchestrator/src/llm_orchestrator/chart_annotation_sanitize.py`                                                            |
| Service-Hook          | `services/llm-orchestrator/src/llm_orchestrator/service.py`                                                                              |
| Pytest + Fixture      | `tests/llm_orchestrator/test_chart_annotation_sanitize.py`, `tests/fixtures/chart_annotations/strategy_signal_chart_annotations_ms.json` |
| Prompt                | `shared/prompts/tasks/strategy_signal_explain.instruction_de.txt`                                                                        |
| Verifikationsskript   | `scripts/verify_ai_strategy_signal_explain.py`                                                                                           |

## Offene Punkte

- **[RISK]** Echte Provider können semantisch unsinnige aber schema-konforme Zahlen liefern — Preis-/Zeit-Filter reduzieren Schaden, eliminieren aber keine inhaltliche Fehlinterpretation.
- **[FUTURE]** Playwright-Screenshot des KI-Layers optional, wenn E2E-Basis dafür ausgebaut wird.
