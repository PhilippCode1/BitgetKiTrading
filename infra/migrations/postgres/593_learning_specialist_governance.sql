-- Spezialisten-Curriculum: Registry-Scopes market_cluster + symbol; Learning-Kontext ohne Policy-Rewrite.

ALTER TABLE app.model_registry_v2 DROP CONSTRAINT IF EXISTS chk_model_registry_v2_scope_type;

ALTER TABLE app.model_registry_v2
    ADD CONSTRAINT chk_model_registry_v2_scope_type CHECK (
        scope_type IN (
            'global',
            'market_family',
            'market_cluster',
            'market_regime',
            'playbook',
            'router_slot',
            'symbol'
        )
    );

COMMENT ON COLUMN app.model_registry_v2.scope_type IS
    'global | market_family | market_cluster (generisch bei duennen Symbol-Daten) | market_regime | playbook | router_slot | symbol (nur bei nachgewiesener Mindestmenge)';

CREATE TABLE IF NOT EXISTS learn.learning_context_signals (
    context_signal_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_kind text NOT NULL CHECK (source_kind IN (
        'shadow',
        'paper',
        'post_trade_review',
        'operator_context',
        'live_outcome'
    )),
    reference_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload_redacted_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    policy_rewrite_forbidden boolean NOT NULL DEFAULT true,
    curriculum_version text NOT NULL DEFAULT 'specialist-curriculum-v1',
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_context_signals_created
    ON learn.learning_context_signals (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_learning_context_signals_source
    ON learn.learning_context_signals (source_kind, created_ts DESC);

COMMENT ON TABLE learn.learning_context_signals IS
    'Kontext fuer Learning (Reviews, Outcomes, Operator-Spiegel); policy_rewrite_forbidden=true erzwingt keine Strategie-Mutation.';
