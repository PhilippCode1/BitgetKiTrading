-- Prompt 45: Katalog kommerzieller Nutzungsmerkmale (Entitlement-Gates pro Feature).

CREATE TABLE IF NOT EXISTS app.commercial_usage_entitlements (
    feature_name text NOT NULL PRIMARY KEY,
    plan_entitlement_key text NOT NULL,
    min_prepaid_balance_list_usd numeric(18, 8) NOT NULL DEFAULT 0,
    description text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_commercial_usage_ent_key_nonempty CHECK (char_length(plan_entitlement_key) >= 1),
    CONSTRAINT chk_commercial_usage_ent_min_nonneg CHECK (min_prepaid_balance_list_usd >= 0)
);

COMMENT ON TABLE app.commercial_usage_entitlements IS
    'Pro Feature: JSON-Schluessel in commercial_plan_definitions.entitlements_json und Mindest-Prepaid (List-USD).';

INSERT INTO app.commercial_usage_entitlements (
    feature_name, plan_entitlement_key, min_prepaid_balance_list_usd, description
)
VALUES (
    'AI_DEEP_ANALYSIS',
    'ai_deep_analysis',
    0.00,
    'Tiefe KI-Erklaerungen (operator-explain, Strategie-/Signal-Analyst).'
)
ON CONFLICT (feature_name) DO NOTHING;

-- Plan-Metadaten: explizite ai_deep_analysis-Flags
UPDATE app.commercial_plan_definitions
SET entitlements_json = entitlements_json || jsonb_build_object('ai_deep_analysis', false)
WHERE plan_id = 'starter';

UPDATE app.commercial_plan_definitions
SET entitlements_json = entitlements_json || jsonb_build_object('ai_deep_analysis', true)
WHERE plan_id = 'professional';

INSERT INTO app.commercial_plan_definitions (
    plan_id, display_name, entitlements_json, llm_monthly_token_cap,
    llm_per_1k_tokens_list_usd, transparency_note
)
VALUES
(
    'free',
    'Free',
    '{"llm":"none","signals_read":true,"ai_deep_analysis":false}'::jsonb,
    0,
    0,
    'Kein KI-Premium; Entitlements bewusst restriktiv (Prompt 45).'
)
ON CONFLICT (plan_id) DO NOTHING;
