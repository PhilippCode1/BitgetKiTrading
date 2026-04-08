-- Prompt 18: Paper-Broker Kern — Schema paper, Tabellen fuer Accounts, Positionen, Orders, Fills, Ledger

CREATE SCHEMA IF NOT EXISTS paper;

CREATE TABLE IF NOT EXISTS paper.accounts (
    account_id uuid PRIMARY KEY,
    currency text NOT NULL DEFAULT 'USDT',
    initial_equity numeric NOT NULL,
    equity numeric NOT NULL,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS paper.positions (
    position_id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES paper.accounts (account_id),
    symbol text NOT NULL,
    side text NOT NULL CHECK (side IN ('long', 'short')),
    qty_base numeric NOT NULL,
    entry_price_avg numeric NOT NULL,
    leverage numeric NOT NULL,
    margin_mode text NOT NULL CHECK (margin_mode IN ('isolated', 'crossed')),
    isolated_margin numeric NOT NULL,
    state text NOT NULL CHECK (state IN ('open', 'partially_closed', 'closed', 'liquidated')),
    opened_ts_ms bigint NOT NULL,
    updated_ts_ms bigint NOT NULL,
    closed_ts_ms bigint,
    liq_price_sim numeric,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_account ON paper.positions (account_id);
CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol_state ON paper.positions (symbol, state);

CREATE TABLE IF NOT EXISTS paper.orders (
    order_id uuid PRIMARY KEY,
    position_id uuid NOT NULL REFERENCES paper.positions (position_id),
    type text NOT NULL CHECK (type IN ('market', 'limit')),
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    qty_base numeric NOT NULL,
    limit_price numeric,
    state text NOT NULL CHECK (state IN ('new', 'filled', 'canceled')),
    created_ts_ms bigint NOT NULL,
    filled_ts_ms bigint
);

CREATE INDEX IF NOT EXISTS idx_paper_orders_position ON paper.orders (position_id);

CREATE TABLE IF NOT EXISTS paper.fills (
    fill_id uuid PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES paper.orders (order_id),
    position_id uuid NOT NULL REFERENCES paper.positions (position_id),
    ts_ms bigint NOT NULL,
    price numeric NOT NULL,
    qty_base numeric NOT NULL,
    liquidity text NOT NULL CHECK (liquidity IN ('maker', 'taker', 'unknown')),
    fee_usdt numeric NOT NULL,
    notional_usdt numeric NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_fills_position ON paper.fills (position_id);

CREATE TABLE IF NOT EXISTS paper.funding_ledger (
    funding_id uuid PRIMARY KEY,
    position_id uuid NOT NULL REFERENCES paper.positions (position_id),
    ts_ms bigint NOT NULL,
    funding_rate numeric NOT NULL,
    position_value_usdt numeric NOT NULL,
    funding_usdt numeric NOT NULL,
    source text NOT NULL CHECK (source IN ('events', 'rest', 'sim'))
);

CREATE INDEX IF NOT EXISTS idx_paper_funding_position ON paper.funding_ledger (position_id);

CREATE TABLE IF NOT EXISTS paper.fee_ledger (
    fee_id uuid PRIMARY KEY,
    position_id uuid NOT NULL REFERENCES paper.positions (position_id),
    ts_ms bigint NOT NULL,
    fee_usdt numeric NOT NULL,
    reason text NOT NULL CHECK (reason IN ('entry', 'exit', 'partial_exit'))
);

CREATE INDEX IF NOT EXISTS idx_paper_fee_position ON paper.fee_ledger (position_id);

CREATE TABLE IF NOT EXISTS paper.contract_config_snapshots (
    symbol text NOT NULL,
    product_type text NOT NULL,
    maker_fee_rate numeric NOT NULL,
    taker_fee_rate numeric NOT NULL,
    size_multiplier numeric NOT NULL DEFAULT 1,
    fund_interval_hours integer NOT NULL DEFAULT 8,
    max_lever integer NOT NULL DEFAULT 125,
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    captured_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, product_type, captured_ts_ms)
);

CREATE INDEX IF NOT EXISTS idx_paper_contract_latest ON paper.contract_config_snapshots (symbol, product_type, captured_ts_ms DESC);
