CREATE SCHEMA IF NOT EXISTS tsdb;

CREATE TABLE IF NOT EXISTS tsdb.trades (
    symbol text NOT NULL,
    trade_id text NOT NULL,
    ts_ms bigint NOT NULL,
    price numeric NOT NULL,
    size numeric NOT NULL,
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, trade_id)
);

CREATE INDEX IF NOT EXISTS idx_tsdb_trades_symbol_ts_ms
    ON tsdb.trades (symbol, ts_ms DESC);

CREATE TABLE IF NOT EXISTS tsdb.ticker (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    source text NOT NULL,
    last_pr numeric,
    bid_pr numeric,
    ask_pr numeric,
    bid_sz numeric,
    ask_sz numeric,
    mark_price numeric,
    index_price numeric,
    funding_rate numeric,
    next_funding_time_ms bigint,
    holding_amount numeric,
    base_volume numeric,
    quote_volume numeric,
    funding_rate_interval text,
    funding_next_update_ms bigint,
    funding_min_rate numeric,
    funding_max_rate numeric,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, ts_ms, source)
);

CREATE INDEX IF NOT EXISTS idx_tsdb_ticker_symbol_ts_ms
    ON tsdb.ticker (symbol, ts_ms DESC);

CREATE TABLE IF NOT EXISTS tsdb.orderbook_topn_snapshots (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    seq bigint,
    checksum bigint,
    bids jsonb NOT NULL,
    asks jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_topn_symbol_ts_ms
    ON tsdb.orderbook_topn_snapshots (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_topn_symbol_seq
    ON tsdb.orderbook_topn_snapshots (symbol, seq DESC);

CREATE TABLE IF NOT EXISTS tsdb.orderbook_levels (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    side text NOT NULL CHECK (side IN ('bid', 'ask')),
    level integer NOT NULL CHECK (level > 0),
    price numeric NOT NULL,
    size numeric NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_levels_symbol_ts_ms
    ON tsdb.orderbook_levels (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_levels_symbol_side_level
    ON tsdb.orderbook_levels (symbol, side, level);
