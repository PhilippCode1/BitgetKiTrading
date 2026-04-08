-- Prompt 09: Live Broker Fills and Exchange Snapshots
CREATE TABLE IF NOT EXISTS live.fills (
    fill_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_order_id uuid NULL,
    exchange_order_id text NULL,
    exchange_trade_id text NOT NULL UNIQUE,
    symbol text NOT NULL,
    side text NOT NULL,
    price numeric NOT NULL,
    size numeric NOT NULL,
    fee numeric NOT NULL,
    fee_coin text NOT NULL,
    is_maker boolean NOT NULL,
    exchange_ts_ms bigint NOT NULL,
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_fills_exchange_order_id ON live.fills (exchange_order_id);
CREATE INDEX IF NOT EXISTS idx_live_fills_symbol_created ON live.fills (symbol, created_ts DESC);

CREATE TABLE IF NOT EXISTS live.exchange_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reconcile_run_id uuid NULL,
    symbol text NOT NULL,
    snapshot_type text NOT NULL CHECK (snapshot_type IN ('orders', 'positions', 'account')),
    raw_data jsonb NOT NULL,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_exchange_snapshots_created ON live.exchange_snapshots (created_ts DESC);

