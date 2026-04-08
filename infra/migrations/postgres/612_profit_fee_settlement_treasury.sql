-- Prompt 16: Kontrolliertes Crypto-/Treasury-Settlement fuer freigegebene Profit-Fee-Statements.
-- Keine Exchange-API-Automatik: manueller Ops-Workflow mit Referenzen und Audit.

CREATE TABLE IF NOT EXISTS app.treasury_settlement_config (
    config_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label text NOT NULL,
    exchange_name text NOT NULL DEFAULT 'bitget',
    target_asset text NOT NULL DEFAULT 'USDT',
    network text NOT NULL DEFAULT 'TRC20',
    destination_hint_public text,
    daily_limit_major_units numeric(24, 8),
    monthly_limit_major_units numeric(24, 8),
    active boolean NOT NULL DEFAULT true,
    manual_execution_only boolean NOT NULL DEFAULT true,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_treasury_settlement_config_label UNIQUE (label),
    CONSTRAINT chk_treasury_config_exchange_len CHECK (char_length(exchange_name) <= 64),
    CONSTRAINT chk_treasury_config_asset_len CHECK (char_length(target_asset) <= 32),
    CONSTRAINT chk_treasury_config_network_len CHECK (char_length(network) <= 64)
);

COMMENT ON TABLE app.treasury_settlement_config IS
    'Ziel-Treasury-Metadaten (keine Secrets/Keys); Ausfuehrung manuell oder externe Ops.';

INSERT INTO app.treasury_settlement_config (
    label,
    destination_hint_public,
    manual_execution_only
)
VALUES (
    'default',
    'Bitget Treasury — Zieladresse/Subkonto in Ops-Dokumentation pflegen',
    true
)
ON CONFLICT (label) DO NOTHING;

CREATE TABLE IF NOT EXISTS app.profit_fee_settlement_request (
    settlement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id uuid NOT NULL REFERENCES app.profit_fee_statement (statement_id) ON DELETE RESTRICT,
    treasury_config_id uuid REFERENCES app.treasury_settlement_config (config_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE RESTRICT,
    fee_amount_cents bigint NOT NULL,
    currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL,
    pipeline_version text NOT NULL DEFAULT 'settlement-pipeline-v1',
    treasury_reviewed_ts timestamptz,
    treasury_reviewed_by text,
    payout_submitted_ts timestamptz,
    payout_submitted_by text,
    external_submission_ref text,
    payout_submission_note text,
    settled_ts timestamptz,
    settled_by text,
    confirmation_ref text,
    settlement_note text,
    failure_reason text,
    cancellation_reason text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_pf_settlement_status CHECK (
        status IN (
            'pending_treasury',
            'approved_for_payout',
            'payout_recorded',
            'settled',
            'cancelled',
            'failed'
        )
    ),
    CONSTRAINT chk_pf_settlement_fee_nonneg CHECK (fee_amount_cents >= 0)
);

-- Maximal ein aktiver (nicht terminaler) Settlement-Versuch pro Statement.
CREATE UNIQUE INDEX IF NOT EXISTS uq_pf_settlement_inflight_statement
    ON app.profit_fee_settlement_request (statement_id)
    WHERE status NOT IN ('cancelled', 'failed', 'settled');

-- Erfolgreiche Abwicklung hoechstens einmal pro Statement.
CREATE UNIQUE INDEX IF NOT EXISTS uq_pf_settlement_settled_statement
    ON app.profit_fee_settlement_request (statement_id)
    WHERE status = 'settled';

CREATE INDEX IF NOT EXISTS idx_pf_settlement_tenant_updated
    ON app.profit_fee_settlement_request (tenant_id, updated_ts DESC);

COMMENT ON TABLE app.profit_fee_settlement_request IS
    'Interne Forderung; Auszahlung/Transfer nur ausserhalb des Gateways oder per manueller Bestaetigung.';

CREATE TABLE IF NOT EXISTS app.profit_fee_settlement_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    settlement_id uuid NOT NULL REFERENCES app.profit_fee_settlement_request (settlement_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    actor text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_pf_settlement_audit_event_len CHECK (char_length(event_type) <= 64)
);

CREATE INDEX IF NOT EXISTS idx_pf_settlement_audit_settlement_ts
    ON app.profit_fee_settlement_audit (settlement_id, created_ts DESC);

COMMENT ON TABLE app.profit_fee_settlement_audit IS
    'Append-only: jeder Workflow-Schritt, revisionssicher.';
