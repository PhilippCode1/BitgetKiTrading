# Strategy Registry (Prompt 22)

Zentrale Verwaltung von Strategien im Schema `learn` mit Lifecycle-Status und Redis-Events.

Wichtig: Das **Strategy Registry** ist nicht identisch mit dem
**Playbook-Register**.

- `learn.strategies` / `learn.strategy_versions`: Lifecycle und Promotion
  konkreter Strategien
- `shared_py.playbook_registry`: deterministische Fachbibliothek fuer
  Strategie-Familien, Suitability, Benchmark-Regeln und Anti-Patterns
- `app.model_registry_v2`: Registry fuer ML-Artefakte / Champion-Runs

Playbooks werden im Signalpfad ueber `playbook_id` / `playbook_family`
gebunden, nicht ueber Statuswechsel im `learn`-Schema.

## Statusmodell

| Status      | Bedeutung (Kurz)                            |
| ----------- | ------------------------------------------- |
| `shadow`    | Inaktiv / Experiment                        |
| `candidate` | Zur Bewertung                               |
| `promoted`  | Live-fähig (Paper-Broker optional filternd) |
| `retired`   | Abgeschaltet                                |

## Erlaubte Übergänge

- `shadow` → `candidate`
- `candidate` → `promoted` (bis Prompt 23: **`manual_override: true`** erforderlich)
- `promoted` → `retired`
- `retired` → `shadow` (Re-Aktivierung)

Jede **explizite** Statusänderung über `POST /registry/strategies/{id}/status`:

- schreibt eine Zeile in `learn.strategy_status_history`
- aktualisiert `learn.strategy_status`
- publiziert **`events:strategy_registry_updated`** mit Snapshot `promoted_strategy_names`

> Beim Anlegen einer Strategie (`POST /registry/strategies`) wird der initiale Status gesetzt und in die History geschrieben, **ohne** Redis-Event (Spec: Event bei Statusänderungen über die Status-API).

## API (learning-engine)

Basis: Port `LEARNING_ENGINE_PORT` (z. B. 8090).

| Methode | Pfad                                   | Zweck                               |
| ------- | -------------------------------------- | ----------------------------------- |
| POST    | `/registry/strategies`                 | Strategie anlegen                   |
| POST    | `/registry/strategies/{id}/versions`   | Version + Definition/Parameter/Risk |
| POST    | `/registry/strategies/{id}/status`     | Status setzen                       |
| GET     | `/registry/strategies?status=promoted` | Liste filtern                       |
| GET     | `/registry/strategies/{id}`            | Detail + Versionen                  |

### Auth

- **learning-engine** (`/registry/*` direkt am Service-Port): fuer Betrieb typischerweise **nicht** oeffentlich exponieren; nur internes Netz / Sidecar.
- **api-gateway** (`GET /v1/registry/strategies`, `.../{id}`, `.../{id}/status`): gehoert zu den **sensiblen** Routen — bei erzwungener Gateway-Auth **JWT** oder **interner API-Key** noetig (`docs/api_gateway_security.md`).

## Environment (learning-engine)

| Variable                           | Pflicht | Beispiel                           | Zweck                                                  |
| ---------------------------------- | ------- | ---------------------------------- | ------------------------------------------------------ |
| `LEARNING_ENGINE_PORT`             | ja      | `8090`                             | HTTP                                                   |
| `STRATEGY_REGISTRY_ENABLED`        | ja      | `true`                             | API ein/aus (503 wenn `false`)                         |
| `STRATEGY_REGISTRY_DEFAULT_STATUS` | ja      | `shadow`                           | Initialstatus bei Create                               |
| `STRATEGY_REGISTRY_EVENT_STREAM`   | ja      | `events:strategy_registry_updated` | muss exakt diesem Stream entsprechen (Redis-Whitelist) |
| `LOG_LEVEL`                        | ja      | `INFO`                             | Logs                                                   |

## Events

- **Stream:** `events:strategy_registry_updated`
- **event_type:** `strategy_registry_updated`
- **payload (Auszug):** `strategy_id`, `name`, `old_status`, `new_status`, `reason`, **`promoted_strategy_names`** (vollständige Liste aller aktuell `promoted` Namen)

## Paper-Broker-Integration

- Lokale Strategy-Klassen (Prompt 20) bleiben maßgeblich für Logik.
- Wenn `STRATEGY_REGISTRY_ENABLED=true`:
  - Consumer abonniert zusätzlich `events:strategy_registry_updated`.
  - Nach jedem Event: In-Memory-Set `promoted_strategy_names`.
  - Vor Auto-Trade: Wenn Set **nicht leer**, nur Strategien mit passendem `StrategyV1.name` (z. B. `BreakoutBoxStrategy`).
  - Wenn Set **leer** → **Fallback: alle erlaubt** (kein hartes Blockieren ohne Snapshot).
- Wenn `STRATEGY_REGISTRY_ENABLED=false` → kein Filter (wie bisher).

| Variable                         | Beispiel                           |
| -------------------------------- | ---------------------------------- |
| `STRATEGY_REGISTRY_ENABLED`      | `false` / `true`                   |
| `STRATEGY_REGISTRY_EVENT_STREAM` | `events:strategy_registry_updated` |

Consumer startet auch bei `PAPER_SIM_MODE=true`, wenn Registry **oder** Strategy-Exec aktiv ist (damit Snapshot ankommt).

## Nächste Schritte

- **Prompt 23:** Promotion-Gates, Health-Metriken, Drift, Empfehlungen — dann `manual_override` für `candidate`→`promoted` optional abschaffen.
