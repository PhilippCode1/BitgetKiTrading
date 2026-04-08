# 24 — Signals-API, Facets und einheitliche Filter

## Pflichtgrundlagen

- **Datei 04:** `docs/chatgpt_handoff/04_API_BFF_ENDPOINT_DOSSIER.md` — Browser → BFF `/api/dashboard/gateway/v1/...` → Gateway; `/v1/signals/*` mit `require_sensitive_auth`.
- **Datei 05:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md` — Persistenz `app.signals_v1`, Lesepfade `recent`, `facets`, `{id}`, `{id}/explain`.

## API-Gateway (kanonisch)

| Methode | Pfad                              | Zweck                                                            |
| ------- | --------------------------------- | ---------------------------------------------------------------- |
| GET     | `/v1/signals/recent`              | Gefilterte Liste (Envelope + `items`, `limit`, `filters_active`) |
| GET     | `/v1/signals/facets`              | Distinct-Werte im Lookback (Envelope + Facet-Arrays)             |
| GET     | `/v1/signals/{signal_id}`         | Detail (404 wenn unbekannt)                                      |
| GET     | `/v1/signals/{signal_id}/explain` | Erklaerung + `explanation_layers` (404 wenn Signal fehlt)        |

**Signal-Contract-Version:** `SIGNAL_API_CONTRACT_VERSION` in `services/api-gateway/src/api_gateway/signal_contract.py` (Stand Umsetzung: **1.2.0**).

## Parametertabelle `GET /v1/signals/recent`

Alle Filter sind **UND**-verknuepft. Leere oder reine Whitespace-Query-Werte werden ignoriert.

| Query-Parameter        | Typ    | Normalisierung / Match                    | Spalte / Quelle                                                                                                                                                                               |
| ---------------------- | ------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `symbol`               | string | upper                                     | `s.symbol`                                                                                                                                                                                    |
| `timeframe`            | string | `normalize_tf_for_db` (z. B. `1h` → `1H`) | `s.timeframe`                                                                                                                                                                                 |
| `direction`            | string | lower                                     | `s.direction`                                                                                                                                                                                 |
| `min_strength`         | number | —                                         | `s.signal_strength_0_100 >=`                                                                                                                                                                  |
| `market_family`        | string | trim                                      | `s.market_family`                                                                                                                                                                             |
| `playbook_id`          | string | trim                                      | `s.playbook_id`                                                                                                                                                                               |
| `playbook_family`      | string | trim                                      | `s.playbook_family`                                                                                                                                                                           |
| `trade_action`         | string | trim + lower                              | `s.trade_action`                                                                                                                                                                              |
| `meta_trade_lane`      | string | trim                                      | `s.meta_trade_lane`                                                                                                                                                                           |
| `regime_state`         | string | trim                                      | `s.regime_state`                                                                                                                                                                              |
| `specialist_router_id` | string | trim                                      | JSON `reasons_json` / `source_snapshot_json` → `specialists.router_arbitration.router_id`                                                                                                     |
| `exit_family`          | string | trim                                      | JSON → `exit_family_effective_primary` (reasons + snapshot)                                                                                                                                   |
| `decision_state`       | string | trim                                      | `s.decision_state`                                                                                                                                                                            |
| `strategy_name`        | string | trim                                      | `s.strategy_name`                                                                                                                                                                             |
| `signal_class`         | string | trim                                      | `s.signal_class`                                                                                                                                                                              |
| `signal_registry_key`  | string | trim                                      | `TRIM(playbook_id) = key OR TRIM(strategy_name) = key` — abgestimmt mit `learn.strategies.name` und Registry-Signalpfad; siehe `docs/cursor_execution/25_strategy_registry_and_ui_linkage.md` |
| `limit`                | int    | 1..500, Default aus Gateway-Settings      | `LIMIT`                                                                                                                                                                                       |

**Antwort-Zusatzfeld:** `filters_active` (bool) — `true`, wenn mindestens einer der obigen Filter (inkl. `min_strength`) gesetzt ist.

**Leerer Listen-Zustand (Envelope):**

- Ohne aktive Filter: `degradation_reason`: `no_signals`, Hinweis auf leere Datenlage / Pipeline.
- Mit aktiven Filtern: `degradation_reason`: `no_signals_filtered`, Hinweis Filter zu lockern.

## Parametertabelle `GET /v1/signals/facets`

| Query           | Typ | Default | Beschreibung                                                                    |
| --------------- | --- | ------- | ------------------------------------------------------------------------------- |
| `lookback_rows` | int | 3000    | 100..20000; distinct jeweils ueber die juengsten N Zeilen nach `analysis_ts_ms` |

**Response-Arrays (alle string[], sortiert):**  
`market_families`, `playbook_families`, `meta_trade_lanes`, `regime_states`, `specialist_routers`, `exit_families`, `symbols`, `timeframes`, `directions`, `decision_states`, `trade_actions`, `strategy_names`, `playbook_ids`, `signal_classes`.

**Leerer Zustand:** Wenn alle Arrays leer: `empty_state: true`, `degradation_reason: no_signal_facets`, `message` / `next_step` setzen — **keine** stille Leer-UI ohne Erklaerung.

## Detail und Explain

- **Detail** und **Explain** nutzen **keine** Listen-Filter — nur `signal_id` im Pfad.
- Filterdisziplin fuer die UI: von der Liste zum Detail nur `signal_id`; zurueck zur Liste behalten die **URL-Query-Parameter** der Konsole-Signalseite den Filterkontext (bereits ueber `consoleHref` / `baseQs`).
- `explain` liefert u. a. `explanation_layers` (persisted / deterministic_engine / live_llm_advisory) gemaess `signal_contract.build_explanation_layers`.

## BFF / Dashboard

- Browser: `fetchSignalsRecent` / `fetchSignalsFacets` → `GET /api/dashboard/gateway/v1/signals/...` (siehe `apps/dashboard/src/lib/api.ts`).
- Konsole: `apps/dashboard/src/app/(operator)/console/signals/page.tsx` — Facet-Banner bei leeren/defekten Facets; Listen-Banner bei leerer Tabelle inkl. Gateway-`message` / `next_step` / Link „Alle Filter zuruecksetzen“ wenn `filters_active`.

## Nachweise (Laufzeit)

```bash
# Gateway (JWT / Operator-Auth wie in eurer Umgebung)
curl -sS -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/signals/facets?lookback_rows=2000" | jq 'keys'
curl -sS -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/signals/recent?limit=5" | jq '{status,empty_state,filters_active,degradation_reason,message}'
curl -sS -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/signals/recent?symbol=BTCUSDT&decision_state=accepted&limit=5" | jq '{filters_active,degradation_reason}'

SIGNAL_ID=…
curl -sS -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/signals/$SIGNAL_ID" | jq '.signal_id,.symbol'
curl -sS -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/signals/$SIGNAL_ID/explain" | jq '.signal_id,.explanation_layers != null'
```

**Unit-Tests (Repo):** `pytest tests/unit/api_gateway/test_db_dashboard_queries.py` (Mock-Conn fuer `fetch_signals_recent`).

## UX-Hinweis `[FUTURE]`

Feldnamen wie `market_family` bleiben in Labels absichtlich **technisch** (Konsistenz mit API/DB). Freundlichere Operator-Bezeichner koennen in einem spaeteren Prompt ergaenzt werden, ohne Query-Namen zu aendern.

## Offene Punkte

- `[TECHNICAL_DEBT]` OpenAPI-JSON ggf. nachziehen, wenn ihr die Datei als Single Source pflegt.
- `[RISK]` `strategy_name` / `playbook_id` sind exakte Matches — Tippfehler in manuellen URLs liefern leere Listen (jetzt mit erklaerender Envelope).
