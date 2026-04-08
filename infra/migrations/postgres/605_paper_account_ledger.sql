-- Prompt 8: Paper-Demo — append-only Konten-Ledger (Einzahlungen, Admin, Reset-Marker).
-- Trennung von positionsgebundenen fee_/funding_ledger; kompatibel mit bestehendem Schema.

CREATE TABLE IF NOT EXISTS paper.account_ledger (
    entry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid NOT NULL REFERENCES paper.accounts (account_id) ON DELETE CASCADE,
    ts_ms bigint NOT NULL,
    amount_usdt numeric NOT NULL,
    balance_after numeric NOT NULL,
    reason text NOT NULL CHECK (
        reason IN (
            'bootstrap',
            'deposit_demo',
            'withdraw_demo',
            'admin_adjustment',
            'admin_reset'
        )
    ),
    note text,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_paper_account_ledger_account_ts
    ON paper.account_ledger (account_id, ts_ms DESC);
