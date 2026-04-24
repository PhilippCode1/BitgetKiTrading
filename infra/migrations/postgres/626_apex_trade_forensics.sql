-- Prompt 68: Golden Record pro Execution (Signal → AI → Risk → Fill), verkettet wie Apex-Ledger.
-- Hinweis: 617 ist apex_audit_ledger; Trade-Forensik ist separat.

CREATE TABLE IF NOT EXISTS app.apex_trade_forensics (
    id bigserial PRIMARY KEY,
    execution_id uuid NOT NULL UNIQUE,
    signal_id uuid NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    prev_chain_checksum bytea NOT NULL CHECK (octet_length(prev_chain_checksum) = 32),
    chain_checksum bytea NOT NULL CHECK (octet_length(chain_checksum) = 32),
    golden_record jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_apex_trade_forensics_signal
    ON app.apex_trade_forensics (signal_id);

CREATE INDEX IF NOT EXISTS idx_apex_trade_forensics_created
    ON app.apex_trade_forensics (created_at DESC);

COMMENT ON TABLE app.apex_trade_forensics IS
    'Goldener Forensik-Record je execution_id; chain_checksum = SHA256(prev || canonical_json(golden_record)).';
