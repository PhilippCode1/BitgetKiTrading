-- Prompt 22: Kunden-Domain-Events (append-only, idempotent pro tenant+key), Read-Model-Cursor.

CREATE TABLE IF NOT EXISTS app.customer_domain_event (
    seq bigserial PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    aggregate_type text NOT NULL,
    event_type text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    correlation_id text,
    idempotency_key text NOT NULL,
    source text NOT NULL DEFAULT 'gateway',
    recorded_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_customer_domain_event_aggregate_len CHECK (
        char_length(aggregate_type) <= 64
    ),
    CONSTRAINT chk_customer_domain_event_event_len CHECK (char_length(event_type) <= 128),
    CONSTRAINT chk_customer_domain_event_idem_len CHECK (char_length(idempotency_key) <= 256),
    CONSTRAINT chk_customer_domain_event_source_len CHECK (char_length(source) <= 64),
    CONSTRAINT uq_customer_domain_event_tenant_idem UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_customer_domain_event_tenant_seq
    ON app.customer_domain_event (tenant_id, seq DESC);

CREATE INDEX IF NOT EXISTS idx_customer_domain_event_tenant_recorded
    ON app.customer_domain_event (tenant_id, recorded_ts DESC);

COMMENT ON TABLE app.customer_domain_event IS
    'Append-only Kundenereignisse (Portal, Wallet, Zahlung, Lifecycle, Billing). '
    'Idempotenz: UNIQUE(tenant_id, idempotency_key) fuer sichere Retries.';

CREATE TABLE IF NOT EXISTS app.customer_read_model_state (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    portal_seq_applied bigint NOT NULL DEFAULT 0,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE app.customer_read_model_state IS
    'Letzte verarbeitete Domain-Event-Seq je Tenant fuer Portal-Read-Model (Catch-up / Monitoring).';

INSERT INTO app.customer_read_model_state (tenant_id, portal_seq_applied)
SELECT tenant_id, 0 FROM app.tenant_commercial_state
ON CONFLICT (tenant_id) DO NOTHING;
