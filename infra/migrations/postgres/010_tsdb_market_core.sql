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

CREATE TABLE IF NOT EXISTS tsdb.ticker (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    source text NOT NULL DEFAULT 'unknown',
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
    PRIMARY KEY (symbol, ts_ms)
);

CREATE TABLE IF NOT EXISTS tsdb.orderbook_top25 (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    seq bigint,
    checksum integer,
    bids_raw jsonb NOT NULL,
    asks_raw jsonb NOT NULL,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, ts_ms)
);

CREATE TABLE IF NOT EXISTS tsdb.orderbook_levels (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    side text NOT NULL CHECK (side IN ('bid', 'ask')),
    level integer NOT NULL CHECK (level > 0),
    price numeric NOT NULL,
    size numeric NOT NULL,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, ts_ms, side, level)
);

CREATE TABLE IF NOT EXISTS tsdb.funding_rate (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    source text NOT NULL DEFAULT 'unknown',
    funding_rate numeric NOT NULL,
    interval_hours integer,
    next_update_ms bigint,
    min_rate numeric,
    max_rate numeric,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, ts_ms)
);

CREATE TABLE IF NOT EXISTS tsdb.open_interest (
    symbol text NOT NULL,
    ts_ms bigint NOT NULL,
    source text NOT NULL DEFAULT 'unknown',
    size numeric NOT NULL,
    ingest_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, ts_ms)
);
