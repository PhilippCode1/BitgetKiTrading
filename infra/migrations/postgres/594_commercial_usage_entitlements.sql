-- Kommerzielle Transparenz: Plaene, Tenant-Zuordnung, Usage-Ledger (ohne versteckte Multiplikatoren)

CREATE TABLE IF NOT EXISTS app.commercial_plan_definitions (
    plan_id text PRIMARY KEY,
    display_name text NOT NULL,
    entitlements_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    llm_monthly_token_cap bigint,
    llm_per_1k_tokens_list_usd numeric(18, 8),
    transparency_note text,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.tenant_commercial_state (
    tenant_id text PRIMARY KEY,
    plan_id text NOT NULL REFERENCES app.commercial_plan_definitions (plan_id),
    budget_cap_usd_month numeric(18, 8),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.usage_ledger (
    ledger_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    event_type text NOT NULL,
    quantity numeric NOT NULL,
    unit text NOT NULL,
    unit_price_list_usd numeric(18, 8),
    line_total_list_usd numeric(18, 8) NOT NULL,
    platform_markup_factor numeric(18, 8) NOT NULL DEFAULT 1.0,
    correlation_id text,
    actor text,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_usage_ledger_markup_neutral CHECK (platform_markup_factor = 1.0)
);

CREATE INDEX IF NOT EXISTS idx_usage_ledger_tenant_created
    ON app.usage_ledger (tenant_id, created_ts DESC);

COMMENT ON TABLE app.commercial_plan_definitions IS
    'Oeffentliche Plan-Metadaten; Preise nur als referenzierte List-Units (keine dynamischen Aufschlaege im Ledger).';

COMMENT ON TABLE app.usage_ledger IS
    'Append-only Nutzungsjournal; line_total_list_usd = nachvollziehbare List-Groesse, markup-Faktor fix 1.0.';

INSERT INTO app.commercial_plan_definitions (
    plan_id, display_name, entitlements_json, llm_monthly_token_cap,
    llm_per_1k_tokens_list_usd, transparency_note
)
VALUES
(
    'starter',
    'Starter',
    '{"llm":"standard","signals_read":true}'::jsonb,
    500000,
    0.00200000,
    'Referenzpreis USD pro 1k LLM-Tokens (List); identisch fuer Starter/Pro, Unterschied nur Cap/Entitlements.'
),
(
    'professional',
    'Professional',
    '{"llm":"standard","signals_read":true,"priority_queue":true}'::jsonb,
    2000000,
    0.00200000,
    'Gleicher Token-Listenpreis wie Starter; mehr inkludierte Tokens — keine versteckte Preisstaffel.'
)
ON CONFLICT (plan_id) DO NOTHING;

INSERT INTO app.tenant_commercial_state (tenant_id, plan_id, budget_cap_usd_month)
VALUES ('default', 'starter', NULL)
ON CONFLICT (tenant_id) DO NOTHING;
