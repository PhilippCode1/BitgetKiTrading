# Signal Engine V1 (Prompt 13)

## Rolle

Der Microservice **signal-engine** kombiniert **ausschliesslich strukturierte** Quellen:

- `features.candle_features` (Feature-Engine)
- `app.structure_state` / `app.structure_events` (Structure-Engine)
- `app.drawings` (Drawing-Engine, aktiv, pro Symbol+TF)
- optional `app.news_items` (News-Engine)

**Keine** Roh-Kerzen-Interpretation und **keine** LLM-Kernlogik. Alle Teilscores sind
deterministisch und in `docs/scoring_model_v1.md` beschrieben.

## Persistenz

Neue Tabelle **`app.signals_v1`** (Migration `070_signals_v1.sql`). Die Legacy-Tabelle
`app.signals` bleibt fuer bestehende FKs (z. B. `demo_trades`) unveraendert; der
Paper-Broker kann spaeter auf `signals_v1` umgestellt werden.

## Eventbus

- **Input:** `events:drawing_updated` (konfigurierbar via `SIGNAL_STREAM`, Default
  muss `events:drawing_updated` sein).
- **Output:** `events:signal_created` als `EventEnvelope` mit `payload` gemaess
  `shared_py.signal_contracts.SIGNAL_EVENT_SCHEMA_VERSION`.

## HTTP API

| Route                                           | Beschreibung       |
| ----------------------------------------------- | ------------------ |
| `GET /health`                                   | inkl. Worker-Stats |
| `GET /signals/latest?symbol=&timeframe=`        | juengstes Signal   |
| `GET /signals/recent?symbol=&timeframe=&limit=` | Liste              |
| `GET /signals/by-id/{uuid}`                     | Einzelabruf        |

Fehlerantworten enthalten keine Stacktraces oder Secrets.

## Konfiguration

Alle Parameter liegen in **`SignalEngineSettings`** (`config.py`), geladen aus ENV.
Die Gewichte `SIGNAL_WEIGHT_*` werden beim Start validiert (**Summe = 1.0**).

## Tests

```bash
pytest -q tests/signal_engine
```

## Start lokal

```bash
cd services/signal-engine
pip install -e .
set DATABASE_URL=...
set REDIS_URL=...
python -m signal_engine.main
```

Health: `curl -s http://localhost:8050/health`  
Signal: `curl -s "http://localhost:8050/signals/latest?symbol=<example_symbol>&timeframe=5m"`  
Redis: `redis-cli XLEN events:signal_created`
