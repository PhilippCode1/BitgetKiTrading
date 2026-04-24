-- Prompt 54: Paper-Broker — tenant_id pro Account, Ledger, Positionen (Isolierung + Gate-Pruefungen)

ALTER TABLE paper.accounts ADD COLUMN IF NOT EXISTS tenant_id text NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS idx_paper_accounts_tenant_id ON paper.accounts (tenant_id);

-- account_ledger: Denormalisierung + Filter ohne Join
ALTER TABLE paper.account_ledger ADD COLUMN IF NOT EXISTS tenant_id text;
UPDATE paper.account_ledger l
SET tenant_id = a.tenant_id
FROM paper.accounts a
WHERE a.account_id = l.account_id
  AND l.tenant_id IS NULL;
UPDATE paper.account_ledger SET tenant_id = 'default' WHERE tenant_id IS NULL;
ALTER TABLE paper.account_ledger ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_paper_account_ledger_tenant
    ON paper.account_ledger (tenant_id, account_id, ts_ms DESC);

-- positions: jede Abfrage kann mit tenant_id eingrenzen
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS tenant_id text;
UPDATE paper.positions p
SET tenant_id = a.tenant_id
FROM paper.accounts a
WHERE a.account_id = p.account_id
  AND p.tenant_id IS NULL;
UPDATE paper.positions SET tenant_id = 'default' WHERE tenant_id IS NULL;
ALTER TABLE paper.positions ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_paper_positions_tenant_state
    ON paper.positions (tenant_id, state);
