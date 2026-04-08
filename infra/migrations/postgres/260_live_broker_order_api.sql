-- Prompt 07: Live Broker private REST auth, signing and idempotent order API

CREATE TABLE IF NOT EXISTS live.orders (
    internal_order_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_internal_order_id uuid NULL REFERENCES live.orders (internal_order_id) ON DELETE SET NULL,
    source_service text NOT NULL,
    symbol text NOT NULL,
    product_type text NOT NULL,
    margin_mode text NOT NULL CHECK (margin_mode IN ('isolated', 'crossed')),
    margin_coin text NOT NULL,
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    trade_side text NULL,
    order_type text NOT NULL CHECK (order_type IN ('limit', 'market')),
    force text NULL,
    reduce_only boolean NOT NULL DEFAULT false,
    size numeric NOT NULL,
    price numeric NULL,
    note text NOT NULL DEFAULT '',
    client_oid text NOT NULL UNIQUE,
    exchange_order_id text NULL,
    status text NOT NULL DEFAULT 'created',
    last_action text NOT NULL DEFAULT 'create',
    last_http_status int NULL,
    last_exchange_code text NULL,
    last_exchange_msg text NULL,
    last_response_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_live_orders_exchange_order_id
    ON live.orders (exchange_order_id)
    WHERE exchange_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_live_orders_symbol_created
    ON live.orders (symbol, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_orders_parent
    ON live.orders (parent_internal_order_id);

CREATE TABLE IF NOT EXISTS live.order_actions (
    action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_order_id uuid NOT NULL,
    action text NOT NULL CHECK (action IN ('create', 'cancel', 'replace', 'query', 'reduce_only')),
    request_path text NOT NULL,
    client_oid text NULL,
    exchange_order_id text NULL,
    http_status int NULL,
    exchange_code text NULL,
    exchange_msg text NULL,
    retry_count int NOT NULL DEFAULT 0,
    request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_order_actions_internal_created
    ON live.order_actions (internal_order_id, created_ts DESC);
