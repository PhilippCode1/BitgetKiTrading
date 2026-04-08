# Datenpipeline: Markt → Engines → Postgres/Redis → Dashboard

Kurzüberblick für Betrieb und Entwicklung (Prompt 11). Detaillierte Live-Terminal-Felder: [`live_terminal.md`](./live_terminal.md).

## Kritische Pfade

| Teilstrecke        | Produzent(en)                         | Persistenz / Push                           | Dashboard-Verbrauch                                                 |
| ------------------ | ------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------- | ------- | -------------------------- |
| Kerzen             | `market-stream` (WS/REST)             | `tsdb.candles`, Redis `events:candle_close` | `GET /v1/live/state` → `candles[]`; SSE-Event `candle`              |
| Microstructure     | `feature-engine`                      | `features.candle_features`                  | `latest_feature`                                                    |
| Struktur/Zeichnung | `structure-engine` → `drawing-engine` | `app.drawings`, `events:drawing_updated`    | `latest_drawings`; SSE `drawing`                                    |
| Signale            | `signal-engine`                       | `app.signals_v1`, `events:signal_created`   | `latest_signal`; SSE `signal`                                       |
| News               | `news-engine`, LLM-Orchestrator       | `app.news_items`, `events:news_scored`      | `latest_news`; SSE `news`                                           |
| Paper              | `paper-broker`                        | `paper.positions`, `events:trade_opened     | updated                                                             | closed` | `paper_state`; SSE `paper` |
| Mark (Paper)       | `market-stream`                       | `tsdb.ticker`                               | `paper_state.mark_price`                                            |
| Online-Drift       | `learning-engine`                     | `learn.online_drift_state`                  | `GET /v1/live/state` → `online_drift`; Ops nutzt `/v1/learning/...` |
| Echtzeit           | —                                     | Redis Streams, Gateway `/v1/live/stream`    | Browser EventSource (`candle`, `signal`, …)                         |

`api-gateway` ist **einziger** BFF fürs Dashboard: keine direkten Browser-Calls zu Microservices.

## Leerer lokaler Stack

- **Kanonische** Migrationen `596`/`597`/`603` sind **No-Op-Platzhalter** (Forward-only); aktive Demo-INSERTs liegen nur unter **`infra/migrations/postgres_demo/`** und laufen nur mit **`BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true`** und zweiter Phase `python infra/migrate.py --demo-seeds` (Compose-`migrate`-Entrypoint macht das automatisch nach dem Hauptlauf). Vertrag: `docs/cursor_execution/11_migrations_and_seed_separation.md`.
- **400** (`learn.online_drift_state`): Seed-Zeile `global`/`ok` bei frischer DB (Schema, kein Markt-Demo).

## Erklärung ohne stille Lücken

`GET /v1/live/state` liefert zusätzlich **`data_lineage`**: pro Segment `has_data`, `producer_de`, `why_empty_de`, `next_step_de` (deutsch). Das Live-Terminal blendet den Block **„Datenfluss je Teilstrecke“** ein.

## Nützliche Compose-Logs

```bash
docker compose --env-file .env.local -f docker-compose.yml logs --tail=200 market-stream feature-engine structure-engine drawing-engine signal-engine news-engine paper-broker learning-engine api-gateway
```
