-- P78: Zeilenfilter pro Mandant; upsert/Report erwarten tenant_id.
ALTER TABLE app.apex_trade_forensics
    ADD COLUMN IF NOT EXISTS tenant_id text NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS idx_apex_trade_forensics_tenant_created
    ON app.apex_trade_forensics (tenant_id, created_at DESC);

COMMENT ON COLUMN app.apex_trade_forensics.tenant_id IS
    'Mandant fuer Report-Filter; Default ''default'' fuer Altbestaende.';
