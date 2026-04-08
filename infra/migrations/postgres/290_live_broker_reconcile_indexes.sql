-- Prompt 09: Live Broker reconcile/read-model indexes

CREATE INDEX IF NOT EXISTS idx_live_fills_internal_created
    ON live.fills (internal_order_id, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_exchange_snapshots_type_symbol_created
    ON live.exchange_snapshots (snapshot_type, symbol, created_ts DESC);
