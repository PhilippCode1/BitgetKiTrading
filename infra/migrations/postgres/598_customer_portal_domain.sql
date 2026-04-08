-- PROMPT 17: Kundenbereich — Profil, Guthaben, Zahlungen, Integrations-Status, Portal-Audit
-- Keine Speicherung von Telegram-Chat-IDs oder Boersen-Keys; nur oeffentliche Hinweise / Status.

CREATE TABLE IF NOT EXISTS app.customer_profile (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    display_name text,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_customer_profile_display_len CHECK (
        display_name IS NULL OR char_length(display_name) <= 120
    )
);

CREATE TABLE IF NOT EXISTS app.customer_wallet (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    prepaid_balance_list_usd numeric(18, 8) NOT NULL DEFAULT 0,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.customer_payment_event (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    amount_list_usd numeric(18, 8) NOT NULL,
    currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL,
    provider text NOT NULL DEFAULT 'manual',
    provider_reference_masked text,
    notes_public text,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customer_payment_tenant_created
    ON app.customer_payment_event (tenant_id, created_ts DESC);

CREATE TABLE IF NOT EXISTS app.customer_integration_snapshot (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    telegram_state text NOT NULL DEFAULT 'unknown',
    telegram_hint_public text,
    broker_state text NOT NULL DEFAULT 'unknown',
    broker_hint_public text,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.customer_portal_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    action text NOT NULL,
    actor text NOT NULL,
    detail_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customer_portal_audit_tenant_created
    ON app.customer_portal_audit (tenant_id, created_ts DESC);

COMMENT ON TABLE app.customer_profile IS 'Anzeigename je Tenant; keine E-Mail/PII-Pflicht.';
COMMENT ON TABLE app.customer_wallet IS 'Prepaid-Guthaben (List-USD); Buchungen separat im usage_ledger.';
COMMENT ON TABLE app.customer_payment_event IS 'Zahlungsereignisse; keine rohen Provider-Tokens.';
COMMENT ON TABLE app.customer_integration_snapshot IS 'Nur Status und oeffentliche Kurzhinweise (keine Secrets).';
COMMENT ON TABLE app.customer_portal_audit IS 'Kundenrelevante Mutationen (Profil etc.), tenant-scoped.';

INSERT INTO app.customer_wallet (tenant_id, prepaid_balance_list_usd)
SELECT tenant_id, 0 FROM app.tenant_commercial_state
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO app.customer_profile (tenant_id)
SELECT tenant_id FROM app.tenant_commercial_state
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO app.customer_integration_snapshot (tenant_id)
SELECT tenant_id FROM app.tenant_commercial_state
ON CONFLICT (tenant_id) DO NOTHING;
