-- KI-Strategievorschläge: Draft-Registry (keine Orderhoheit; Promotion nur protokolliert).

CREATE TABLE IF NOT EXISTS app.ai_strategy_proposal_draft (
    draft_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_ts timestamptz NOT NULL DEFAULT now(),
    operator_actor text NOT NULL DEFAULT 'unknown',
    signal_id text NULL,
    symbol text NOT NULL DEFAULT '',
    timeframe text NOT NULL DEFAULT '',
    lifecycle_status text NOT NULL DEFAULT 'draft',
    proposal_payload_jsonb jsonb NOT NULL,
    validation_report_jsonb jsonb NULL,
    promotion_target_requested text NULL,
    human_promotion_ack boolean NOT NULL DEFAULT false,
    human_promotion_ack_ts timestamptz NULL,
    CONSTRAINT chk_ai_prop_lifecycle CHECK (lifecycle_status IN (
        'draft',
        'validation_passed',
        'validation_failed',
        'promotion_requested',
        'retracted'
    )),
    CONSTRAINT chk_ai_prop_promo_target CHECK (
        promotion_target_requested IS NULL
        OR promotion_target_requested IN (
            'paper_sandbox',
            'shadow_observe',
            'live_requires_full_gates'
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_ai_strategy_proposal_draft_signal_ts
    ON app.ai_strategy_proposal_draft (signal_id, created_ts DESC);

CREATE INDEX IF NOT EXISTS ix_ai_strategy_proposal_draft_created_ts
    ON app.ai_strategy_proposal_draft (created_ts DESC);

COMMENT ON TABLE app.ai_strategy_proposal_draft IS
    'LLM-generierte Strategie-/Szenario-Entwürfe mit Chart-Annotationen. '
    'Kein automatischer Orderpfad: lifecycle_status und promotion_* sind nur Governance-Protokoll; '
    'Umsetzung in Paper/Shadow/Live erfordert separate Produkt-Freigaben.';
