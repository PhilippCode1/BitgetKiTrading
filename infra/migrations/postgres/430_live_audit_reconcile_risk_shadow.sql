-- Prompt 08: Audit-Verknuepfung Reconcile-Laeufe, normalisierte Risk-/Shadow-Live-Zeilen,
-- Fill-Herkunft, referentielle Integritaet order_actions, Indizes fuer Forensik.

CREATE TABLE IF NOT EXISTS live.reconcile_runs (
    reconcile_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_ts timestamptz NOT NULL DEFAULT now(),
    completed_ts timestamptz NULL,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    trigger_reason text NOT NULL DEFAULT '',
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_live_reconcile_runs_started
    ON live.reconcile_runs (started_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_reconcile_runs_status_started
    ON live.reconcile_runs (status, started_ts DESC);

ALTER TABLE live.reconcile_snapshots
    ADD COLUMN IF NOT EXISTS reconcile_run_id uuid NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_live_reconcile_snapshots_reconcile_run'
    ) THEN
        ALTER TABLE live.reconcile_snapshots
            ADD CONSTRAINT fk_live_reconcile_snapshots_reconcile_run
            FOREIGN KEY (reconcile_run_id) REFERENCES live.reconcile_runs (reconcile_run_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_live_reconcile_snapshots_run_created
    ON live.reconcile_snapshots (reconcile_run_id, created_ts DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_live_exchange_snapshots_reconcile_run'
    ) THEN
        ALTER TABLE live.exchange_snapshots
            ADD CONSTRAINT fk_live_exchange_snapshots_reconcile_run
            FOREIGN KEY (reconcile_run_id) REFERENCES live.reconcile_runs (reconcile_run_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS live.shadow_live_assessments (
    assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_decision_id uuid NOT NULL,
    source_signal_id text NULL,
    symbol text NOT NULL,
    match_ok boolean NOT NULL,
    gate_blocked boolean NOT NULL DEFAULT false,
    protocol_version text NULL,
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_live_shadow_live_assessments_execution
        FOREIGN KEY (execution_decision_id)
        REFERENCES live.execution_decisions (execution_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_live_shadow_live_assessments_execution
        UNIQUE (execution_decision_id)
);

CREATE INDEX IF NOT EXISTS idx_live_shadow_live_assessments_symbol_created
    ON live.shadow_live_assessments (symbol, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_shadow_live_assessments_match_gate
    ON live.shadow_live_assessments (match_ok, gate_blocked, created_ts DESC);

CREATE TABLE IF NOT EXISTS live.execution_risk_snapshots (
    execution_decision_id uuid PRIMARY KEY,
    trade_action text NULL,
    decision_state text NULL,
    primary_reason text NULL,
    reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    detail_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_live_execution_risk_snapshots_execution
        FOREIGN KEY (execution_decision_id)
        REFERENCES live.execution_decisions (execution_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_live_execution_risk_trade_action_created
    ON live.execution_risk_snapshots (trade_action, created_ts DESC)
    WHERE trade_action IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_live_execution_risk_decision_state_created
    ON live.execution_risk_snapshots (decision_state, created_ts DESC);

ALTER TABLE live.fills
    ADD COLUMN IF NOT EXISTS ingest_source text NOT NULL DEFAULT 'exchange';

CREATE INDEX IF NOT EXISTS idx_live_fills_ingest_created
    ON live.fills (ingest_source, created_ts DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_live_order_actions_order'
    ) THEN
        ALTER TABLE live.order_actions
            ADD CONSTRAINT fk_live_order_actions_order
            FOREIGN KEY (internal_order_id) REFERENCES live.orders (internal_order_id)
            ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_live_execution_decisions_source_signal_created
    ON live.execution_decisions (source_signal_id, created_ts DESC)
    WHERE source_signal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_live_execution_decisions_shadow_gate_created
    ON live.execution_decisions (created_ts DESC)
    WHERE decision_reason = 'shadow_live_divergence_gate';
