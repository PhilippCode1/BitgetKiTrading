-- Prompt 06: Live Broker Service (shadow intake, reconcile, persistence)

CREATE SCHEMA IF NOT EXISTS live;

CREATE TABLE IF NOT EXISTS live.execution_decisions (
    execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_service text NOT NULL,
    source_signal_id text NULL,
    symbol text NOT NULL,
    timeframe text NULL,
    direction text NOT NULL CHECK (direction IN ('long', 'short', 'neutral')),
    requested_runtime_mode text NOT NULL CHECK (requested_runtime_mode IN ('shadow', 'live')),
    effective_runtime_mode text NOT NULL CHECK (effective_runtime_mode IN ('shadow', 'live')),
    decision_action text NOT NULL CHECK (
        decision_action IN ('shadow_recorded', 'blocked', 'live_candidate_recorded')
    ),
    decision_reason text NOT NULL,
    order_type text NOT NULL DEFAULT 'market' CHECK (order_type IN ('market', 'limit')),
    leverage int NULL CHECK (leverage IS NULL OR leverage BETWEEN 7 AND 75),
    approved_7x boolean NOT NULL DEFAULT false,
    qty_base numeric NULL,
    entry_price numeric NULL,
    stop_loss numeric NULL,
    take_profit numeric NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_execution_decisions_created
    ON live.execution_decisions (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_execution_decisions_symbol_created
    ON live.execution_decisions (symbol, created_ts DESC);

CREATE TABLE IF NOT EXISTS live.paper_reference_events (
    reference_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id text NOT NULL,
    dedupe_key text NOT NULL UNIQUE,
    event_type text NOT NULL CHECK (event_type IN ('trade_opened', 'trade_updated', 'trade_closed')),
    position_id text NOT NULL,
    symbol text NOT NULL,
    state text NULL,
    qty_base numeric NULL,
    reason text NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_paper_reference_created
    ON live.paper_reference_events (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_paper_reference_symbol_created
    ON live.paper_reference_events (symbol, created_ts DESC);

CREATE TABLE IF NOT EXISTS live.reconcile_snapshots (
    reconcile_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status text NOT NULL CHECK (status IN ('ok', 'degraded', 'fail')),
    runtime_mode text NOT NULL CHECK (runtime_mode IN ('paper', 'shadow', 'live')),
    upstream_ok boolean NOT NULL,
    shadow_enabled boolean NOT NULL,
    live_submission_enabled boolean NOT NULL,
    decision_counts_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_reconcile_snapshots_created
    ON live.reconcile_snapshots (created_ts DESC);
