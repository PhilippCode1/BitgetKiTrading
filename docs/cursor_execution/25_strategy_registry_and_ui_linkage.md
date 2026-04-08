# 25 — Strategie-Registry, UI und Signalpfad (finale Kopplung)

## Pflichtgrundlagen

- **05:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md` — Registry vs. `app.signals_v1`, getrennte APIs, Kopplung ueber Namen.
- **06:** `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md` — Registry ist **kein** LLM; KI auf Signal-/Operator-Pfaden.
- **19:** `docs/cursor_execution/19_learning_engine_and_strategy_registry.md` — `learn.strategies`, Lifecycle, Rolling-Scores, `signal_path_playbooks`.

## Semantik: ein Registry-Name, zwei Signal-Spalten

| Begriff           | Bedeutung                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Registry-Name** | `learn.strategies.name` (eindeutiger Schluessel in der Registry-Liste)                                                         |
| **Signal-Match**  | Eine Zeile in `app.signals_v1` zaehlt, wenn `TRIM(playbook_id) = Registry-Name` **ODER** `TRIM(strategy_name) = Registry-Name` |

**Wichtig:** Das ist **kein** `COALESCE(playbook_id, strategy_name)` pro Zeile fuer die Zaehlung. Eine Zeile mit `playbook_id=A` und `strategy_name=B` wird **sowohl** fuer Registry-Name A **als auch** fuer B gezaehlt, wenn beide Spalten gesetzt und unterschiedlich sind — entspricht der ODER-Logik.

## Gateway-Endpunkte

| Methode | Pfad                                  | Rolle                                                                |
| ------- | ------------------------------------- | -------------------------------------------------------------------- |
| GET     | `/v1/registry/strategies`             | `items` (Registry-Zeilen) + `signal_path_playbooks` (nur Signalpfad) |
| GET     | `/v1/registry/strategies/{id}`        | Detail inkl. `performance_rolling`, `signal_path`, `ai_explanations` |
| GET     | `/v1/registry/strategies/{id}/status` | Kompakter Lifecycle-Status                                           |

## Response-Felder (Detail, Auszug)

- **`performance_rolling`:** Liste aus `learn.strategy_scores_rolling`; kann leer sein.
- **`performance_rolling_empty`:** `true`, wenn keine Rolling-Zeilen — **expliziter** Leerzustand.
- **`performance_rolling_empty_hint_de`:** Kurzer deutscher Hinweis (kein Signalfehler, Learning-Pipeline).
- **`signal_path.registry_key`:** Entspricht `learn.strategies.name` (Kopplung zur Signalseite).
- **`signal_path.matching_signal_count` / `last_signal_ts_ms`:** Aggregation mit ODER-Match (siehe oben).
- **`signal_path.signals_list_query_param`:** Kanonisch `signal_registry_key`.
- **`signal_path.signals_link_hint_de`:** Erklaert Unterschied zu reinem `playbook_id`-Filter.

## Liste (`items[]`)

Zusaetzlich zu **19**:

- **`rolling_snapshot_empty`:** `true`, wenn kein JOIN auf die 30d-Rolling-Zeile in der Listen-Query — PF/Win in der Tabelle dann typischerweise „—“; UI zeigt eine kurze Fussnote.

## Signalseite / `GET /v1/signals/recent`

| Query                     | Semantik                                                                                                                           |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `playbook_id`             | Nur `s.playbook_id` (exakt, trim)                                                                                                  |
| `strategy_name`           | Nur `s.strategy_name` (exakt, trim)                                                                                                |
| **`signal_registry_key`** | **`playbook_id = key OR strategy_name = key`** — **gleiche Logik** wie Registry-Zaehlung und empfohlene Links aus der Strategie-UI |

Siehe auch `docs/cursor_execution/24_signals_api_and_facets.md` (Parametertabelle).

## UI-Logik (Dashboard)

| Seite                      | Verhalten                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/console/strategies`      | Tabelle + Rolling-Hinweis; Panel „Signalpfad ohne Registry“ mit Link `?signal_registry_key=…`                                                     |
| `/console/strategies/[id]` | Link „Signale zu diesem Registry-Namen“ mit `signal_registry_key`; Performance-Leerzustand mit Gateway-Hinweis; leere Versionen/Historie mit Text |
| `/console/signals`         | Liest `signal_registry_key` aus der URL und reicht ihn an das Gateway weiter                                                                      |

## Nachweise

```bash
# Gateway (Operator-JWT)
curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/registry/strategies" | jq '.items[0] | {name, signal_path_signal_count, rolling_snapshot_empty}'
curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/registry/strategies/<UUID>" | jq '.signal_path, .performance_rolling_empty'
curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/signals/recent?signal_registry_key=<name>&limit=5" | jq '.items | length'

pytest tests/unit/api_gateway/test_db_dashboard_queries.py -q
pnpm --dir apps/dashboard check-types
pytest tests/integration/test_http_stack_integration.py -k strategy_registry -m integration -q
```

## Offene Punkte

- `[FUTURE]` Auto-Seed von `learn.strategies` aus beobachteten Signal-Schluesseln (Policy/Audit) — siehe **19**.
- `[TECHNICAL_DEBT]` Sehr grosse `signals_v1`: Aggregations-Performance (Materialized View / Cache).
