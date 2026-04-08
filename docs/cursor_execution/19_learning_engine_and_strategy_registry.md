# 19 — Learning-Engine, `learn.strategies` und Gateway-Registry

## Ziel

**Stabile Strategie-Registry** (UUID `strategy_id`, eindeutiger `name`, Lifecycle-Status, Versionen, Rolling-Metriken) mit **konsistenter** Anbindung an den **Signalpfad** (`app.signals_v1.playbook_id` / `strategy_name`). Die Konsole `/console/strategies` wirkt nicht mehr „leer“, wenn Signale bereits Playbooks zeigen — **ohne** echte Registry-Zeilen werden **Signal-only-Keys** separat gelistet.

## Schichten (Trennung)

| Schicht                  | Quelle                                                      | Inhalt                                                                                    |
| ------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **Strategie-Metadaten**  | `learn.strategies`, `learn.strategy_versions`, `scope_json` | Name, Beschreibung, Geltungsbereich, Versionen                                            |
| **Lifecycle**            | `learn.strategy_status`, `learn.strategy_status_history`    | `promoted` \| `candidate` \| `shadow` \| `retired` \| **`not_set`** (keine Status-Zeile)  |
| **Laufzeit-Performance** | `learn.strategy_scores_rolling`                             | Fenster (`time_window`) + `metrics_json` — **nicht** mit KI-Texten vermischt              |
| **Signalpfad-Abgleich**  | `app.signals_v1`                                            | Zählung/letzter Zeitstempel: `playbook_id` oder `strategy_name` = `learn.strategies.name` |
| **KI-Erklärungen**       | LLM-/Signal-Pfade                                           | **Nicht** in der Registry-JSON; Detailseite verweist auf Signale / Operator-Explain       |

## Gateway-Endpunkte (Lesen)

| Methode | Pfad                                  | Implementierung                                                                                                    |
| ------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| GET     | `/v1/registry/strategies`             | `routes_registry_proxy.registry_strategies` → `fetch_strategies_registry` + `fetch_signal_path_playbooks_unlinked` |
| GET     | `/v1/registry/strategies/{id}`        | `fetch_strategy_detail` (inkl. `performance_rolling`, `signal_path`, `ai_explanations`)                            |
| GET     | `/v1/registry/strategies/{id}/status` | `fetch_strategy_status_row` (+ `lifecycle_status`)                                                                 |

**Learning-Engine** (intern, nicht BFF-Standard): `GET /registry/strategies` im Service — Dashboard nutzt primär das **Gateway** (einheitliches Envelope + erweiterte Joins).

## Statusmodell (final)

**Lifecycle (`status` in Liste, `lifecycle_status` im Detail):**

- `promoted`, `candidate`, `shadow`, `retired` — aus `learn.strategy_status.current_status`
- **`not_set`** — keine Zeile in `learn.strategy_status` (früher teils als `unknown` ausgeliefert)

**Listen-Zeile (`registry_row_kind`):**

- `registry` — normale `learn.strategies`-Zeile
- `signal_path_only` — nur in `signal_path_playbooks[]` (kein passender `learn.strategies.name`)

## Beispiel: Strategie-Liste (Auszug)

```json
{
  "status": "ok",
  "empty_state": false,
  "message": null,
  "items": [
    {
      "strategy_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "trend_core_v2",
      "description": "",
      "status": "candidate",
      "latest_version": "1.0.0",
      "scope_json": {},
      "rolling_pf": 1.12,
      "rolling_win_rate": 0.55,
      "rolling_metrics_json": {},
      "rolling_time_window": "30d",
      "created_ts": "2026-01-01T12:00:00+00:00",
      "registry_row_kind": "registry",
      "signal_path_signal_count": 42,
      "signal_path_last_signal_ts_ms": 1710000000000
    }
  ],
  "signal_path_playbooks": [
    {
      "playbook_key": "legacy_playbook_x",
      "playbook_family": "trend",
      "signal_count": 15,
      "last_signal_ts_ms": 1709900000000,
      "registry_row_kind": "signal_path_only"
    }
  ]
}
```

**Leerfall nur wenn** `items` und `signal_path_playbooks` leer sind; sonst Hinweis-`message`, wenn nur Signale ohne Registry.

## Beispiel: Strategie-Detail (Auszug)

```json
{
  "strategy_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "trend_core_v2",
  "current_status": "candidate",
  "lifecycle_status": "candidate",
  "performance_rolling": [
    {
      "time_window": "30d",
      "metrics_json": { "profit_factor": 1.1, "win_rate": 0.52 },
      "updated_ts": "2026-04-01T10:00:00+00:00"
    }
  ],
  "signal_path": {
    "matching_signal_count": 42,
    "last_signal_ts_ms": 1710000000000,
    "match_rule_de": "Zaehlung aller app.signals_v1-Zeilen, bei denen playbook_id oder strategy_name exakt dem Registry-Namen entspricht."
  },
  "ai_explanations": {
    "availability": "none",
    "hint_de": "Strategie-spezifische KI-Erklaerungen … Nutze die Signalseite und LLM-Operator-Pfade …"
  }
}
```

## UI

- **`/console/strategies`**: Tabelle mit Lifecycle, Rolling-Kennzahlen, **Signalpfad-Spalte**; darunter Panel **„Im Signalpfad sichtbar, ohne Registry-Zeile“** mit Link `?playbook_id=…` zur Signalseite.
- **`/console/strategies/[id]`**: Abschnitte **Status & Lifecycle**, **Metadaten**, **Rolling-Performance**, **Signalpfad**, **KI-Erklärungen** (Hinweis, kein LLM-JSON).

## Nachweise

```powershell
# Gateway (mit Operator-JWT)
curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/registry/strategies" | jq '.items,.signal_path_playbooks,.message'
curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/registry/strategies/<UUID>" | jq '.lifecycle_status,.performance_rolling,.signal_path'

pnpm check-types
pytest tests/integration/test_http_stack_integration.py -k "strategy_registry" -m integration -q
```

## Verknüpfung zu Signalen / KI

- **Signale:** Filter `playbook_id` entspricht Registry-**name** (String-Vergleich), siehe `console/signals` URL-Parameter.
- **KI:** Operator- und Strategy-Signal-Explain (`/v1/llm/operator/*`, Signal-Detail-UI) bleiben **getrennt** von `GET /v1/registry/*`.

## Offene Punkte

- `[FUTURE]` Automatisches Anlegen von `learn.strategies` aus beobachteten Playbooks (Policy + Audit) statt nur Anzeige.
- `[TECHNICAL_DEBT]` Performance der Signal-Aggregation bei sehr großen `signals_v1` — ggf. materialisierte Sicht oder Cache (Monitor-Datenfrische).
