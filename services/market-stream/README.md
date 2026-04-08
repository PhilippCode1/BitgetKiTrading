# market-stream

## Purpose

Public Bitget Futures WS/REST ingestion with reconnect, ping/pong, outbound
rate-guard and gap-fill hooks.

## Responsibilities

- Connects to the Bitget public WebSocket and keeps a default `ticker`
  subscription for `<example_symbol>` alive.
- Enforces the Bitget outbound limit of max 10 messages per second, including
  ping and subscribe/unsubscribe.
- Publishes normalized events into Redis Streams and can optionally persist raw
  events into Postgres.
- Maintains candle collections for `1m`, `5m`, `15m`, `1H` and `4H`, including
  initial REST load, candle-close events and retention cleanup.
- Maintains local L2 orderbook state with `books` plus `books5` recovery,
  checksum verification, seq handling and slippage metrics.
- Persists trades, ticker/funding/OI and orderbook top-N snapshots into `tsdb`.
- Triggers REST gap-fill on reconnect, stale data and future sequence gaps (pro Kanal),
  inkl. optional `ticker` + `merge-depth`, Hook fuer REST-Ticker-Refresh und Orderbuch-Resync.
- Publiziert `events:market_feed_health` fuer Downstream-Gates; `/ready` prueft `data_freshness`.

## Dependencies

- Redis
- Postgres
- Shared Bitget config from `shared_py.bitget`
- Shared Eventbus contracts from `shared_py.eventbus`

## Input/Output Events

- Input Events: Bitget public WS frames, Bitget market REST responses for
  gap-fill.
- Output Events:
  - Eventbus envelopes in `events:market_tick`, `events:candle_close` and
    `events:funding_update`
  - optional raw rows in Postgres table `raw_events`
  - optional legacy/debug raw mirror in Redis stream `stream:market:raw`

## Required ENV Keys

- `MARKET_STREAM_PORT`
- `MARKET_STREAM_WS_MODE`
- `MARKET_STREAM_ENABLE_RAW_PERSIST`
- `BITGET_CANDLE_INITIAL_LOAD_LIMIT`
- `BITGET_CANDLE_KLINE_TYPE`
- `ORDERBOOK_MAX_LEVELS`
- `ORDERBOOK_CHECKSUM_LEVELS`
- `ORDERBOOK_RESYNC_ON_MISMATCH`
- `SLIPPAGE_SIZES_USDT`
- `OI_SNAPSHOT_INTERVAL_SEC`
- `FUNDING_SNAPSHOT_INTERVAL_SEC`
- `SYMBOL_PRICE_SNAPSHOT_INTERVAL_SEC`
- `TSDB_RETENTION_DAYS_CANDLES_1M`
- `TSDB_RETENTION_DAYS_CANDLES_5M`
- `TSDB_RETENTION_DAYS_CANDLES_15M`
- `TSDB_RETENTION_DAYS_CANDLES_1H`
- `TSDB_RETENTION_DAYS_CANDLES_4H`
- `BITGET_API_BASE_URL`
- `BITGET_WS_PUBLIC_URL`
- `BITGET_PRODUCT_TYPE`
- `BITGET_SYMBOL`
- `BITGET_DEMO_ENABLED`
- `BITGET_DEMO_REST_BASE_URL`
- `BITGET_DEMO_WS_PUBLIC_URL`
- `BITGET_DEMO_PAPTRADING_HEADER`
- `REDIS_URL`
- `EVENTBUS_DEFAULT_BLOCK_MS`
- `EVENTBUS_DEFAULT_COUNT`
- `EVENTBUS_DEDUPE_TTL_SEC`
- `DATABASE_URL`
- `LOG_LEVEL`

## Runtime Endpoints

- `GET /health`: runtime status and connection state.
- `GET /stats`: subscriptions, sequences, candle status and event timestamps.

## Notes

- Only public WS channels are used in this prompt.
- Private channels, login and order flows remain out of scope.
- `python -m market_stream.main` starts the FastAPI health app and the WS
  background runtime.
- Candle rows are stored in `tsdb.candles` and close events are published to
  `events:candle_close` as `EventEnvelope`.
- Ticker snapshots publish `events:market_tick`; funding snapshots publish
  `events:funding_update` when funding data is present.
- Slippage metrics are published to `stream:market:slippage_metrics`.
- DB schema migrations are applied centrally via `python infra/migrate.py`.
