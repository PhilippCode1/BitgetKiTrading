-- Live-Broker: Multi-Family-Metadaten an Orders, Execution-Binding, Operator-Release, Audit-Journal

ALTER TABLE live.orders ADD COLUMN IF NOT EXISTS market_family text NULL;
ALTER TABLE live.orders ADD COLUMN IF NOT EXISTS margin_account_mode text NULL;
ALTER TABLE live.orders ADD COLUMN IF NOT EXISTS source_execution_decision_id uuid NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_live_orders_source_execution'
    ) THEN
        ALTER TABLE live.orders
            ADD CONSTRAINT fk_live_orders_source_execution
            FOREIGN KEY (source_execution_decision_id)
            REFERENCES live.execution_decisions (execution_id);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_live_orders_source_execution
    ON live.orders (source_execution_decision_id)
    WHERE source_execution_decision_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_live_orders_market_family_symbol
    ON live.orders (market_family, symbol, created_ts DESC)
    WHERE market_family IS NOT NULL;

CREATE TABLE IF NOT EXISTS live.execution_operator_releases (
    execution_id uuid PRIMARY KEY
        REFERENCES live.execution_decisions (execution_id) ON DELETE CASCADE,
    released_ts timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL DEFAULT 'internal-api',
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS live.execution_journal (
    journal_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_decision_id uuid NULL
        REFERENCES live.execution_decisions (execution_id) ON DELETE SET NULL,
    internal_order_id uuid NULL
        REFERENCES live.orders (internal_order_id) ON DELETE SET NULL,
    phase text NOT NULL CHECK (phase IN (
        'execution_decision',
        'operator_release',
        'order_submit',
        'order_exchange_ack',
        'fill',
        'reconcile',
        'close'
    )),
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_execution_journal_exec_created
    ON live.execution_journal (execution_decision_id, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_execution_journal_order_created
    ON live.execution_journal (internal_order_id, created_ts DESC);
