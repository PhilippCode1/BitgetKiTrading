# feature-engine

## Purpose

Feature-Berechnung aus Candles, Trades und Orderbook-Daten fuer Signal-, Drawing- und Learning-Pipelines.

## Responsibilities

- Konsumiert `events:candle_close` ueber eine Redis Consumer Group.
- Laedt begrenzte Candle-History aus `tsdb.candles`.
- Berechnet deterministische Candle-Features pro Symbol und Timeframe.
- Joint punkt-in-time Markt-Kontext aus `tsdb.orderbook_levels`,
  `tsdb.funding_rate` und `tsdb.open_interest` an `candle_close.exchange_ts_ms`.
- Nutzt `tsdb.ticker` nur als sichtbaren Fallback fuer Spread/Top-of-Book, falls
  kein Orderbook-Snapshot verfuegbar ist; fehlende Slippage-Proxies bleiben
  dabei absichtlich `NULL`.
- Persistiert Ergebnisse nach `features.candle_features`.
- Liefert die neuesten bzw. gezielten Feature-Rows per HTTP aus.

## Dependencies

- Redis
- Postgres

## Input/Output Events

- Input Events: `events:candle_close`
- Output Events: persistierte Feature-Rows; Fehlerfaelle gehen nach `events:dlq`

## Required ENV Keys

- `REDIS_URL`
- `DATABASE_URL`
- `FEATURE_ENGINE_PORT`
- `FEATURE_STREAM`
- `FEATURE_GROUP`
- `FEATURE_CONSUMER`
- `FEATURE_LOOKBACK_CANDLES`
- `FEATURE_ATR_WINDOW`
- `FEATURE_RSI_WINDOW`
- `FEATURE_VOLZ_WINDOW`
- `FEATURE_MAX_EVENT_AGE_MS`
- `LOG_LEVEL`

## Runtime Endpoints

- `GET /health`
- `GET /features/latest?symbol=<example_symbol>&timeframe=1m`
- `GET /features/at?symbol=<example_symbol>&timeframe=1m&start_ts_ms=...`

## Notes

- Prompt 10 persistiert feste Spalten `atr_14`, `rsi_14` und `vol_z_50`; die
  zugehoerigen ENV-Windows muessen deshalb aktuell `14`, `14` und `50` bleiben.
- Seit Prompt 13 schreibt jede Feature-Row zusaetzlich `feature_schema_version`
  und `feature_schema_hash`, damit Inferenz und Learning denselben maschinenlesbaren
  Vertrag pruefen koennen.
- `FEATURE_MAX_EVENT_AGE_MS` gate't verspätete oder offensichtlich kaputte
  `candle_close`-Inputs vor der Persistenz.
- Multi-TF-Konfluenz nutzt die letzte bekannte `trend_dir` pro Timeframe
  (`1m`, `5m`, `15m`, `1H`, `4H`); fehlende Timeframes werden neutral gewertet.
- Prompt 14 erweitert den Vertrag um `spread_bps`, Top-25-Depth,
  Slippage-Proxies (`impact_*_bps_*`), `execution_cost_bps`,
  `volatility_cost_bps`, `funding_rate_bps`, `funding_cost_bps_window`,
  `open_interest_change_pct` sowie `*_age_ms`- und `*_source`-Felder.
- Die neuen Quellen werden nicht imputiert: fehlende oder nur per Ticker
  approximierte Liquidity-Daten bleiben fuer Signal-/Learning-Gates als
  `liquidity_source != orderbook_levels` bzw. `NULL` sichtbar.
