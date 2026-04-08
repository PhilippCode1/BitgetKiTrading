CREATE SCHEMA IF NOT EXISTS tsdb;

CREATE TABLE IF NOT EXISTS tsdb.candles (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    start_ts_ms bigint NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    base_vol numeric NOT NULL,
    quote_vol numeric NOT NULL,
    usdt_vol numeric NOT NULL,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, timeframe, start_ts_ms)
);

CREATE INDEX IF NOT EXISTS idx_tsdb_candles_symbol_timeframe_start
    ON tsdb.candles (symbol, timeframe, start_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_candles_ingest_ts_ms
    ON tsdb.candles (ingest_ts_ms DESC);
