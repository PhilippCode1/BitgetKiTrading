-- Prompt 23: Gemeinsame Exit-Plaene fuer Live-Broker

CREATE TABLE IF NOT EXISTS live.exit_plans (
    plan_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    root_internal_order_id uuid NOT NULL UNIQUE REFERENCES live.orders (internal_order_id) ON DELETE CASCADE,
    source_signal_id text NULL,
    symbol text NOT NULL,
    side text NOT NULL CHECK (side IN ('long', 'short')),
    timeframe text NULL,
    state text NOT NULL CHECK (state IN ('pending', 'active', 'closing', 'closed', 'cancelled', 'invalid')),
    entry_price numeric NULL,
    initial_qty numeric NULL,
    remaining_qty numeric NULL,
    stop_plan_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    tp_plan_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_market_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_decision_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_reason text NULL,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    closed_ts timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_live_exit_plans_state_updated
    ON live.exit_plans (state, updated_ts ASC);

CREATE INDEX IF NOT EXISTS idx_live_exit_plans_symbol_state
    ON live.exit_plans (symbol, state, updated_ts ASC);
