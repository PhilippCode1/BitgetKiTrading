-- TimesFM vs. War-Room-Konsens: Audit fuer spaeteres RL / Outcome-Labeling (Phase 2/6).

CREATE TABLE IF NOT EXISTS learn.tsfm_war_room_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_ts_ms bigint NOT NULL,
    symbol text NOT NULL,
    forecast_sha256 text,
    tsfm_direction text,
    tsfm_confidence_0_1 double precision,
    tsfm_horizon_ticks integer,
    quant_action text,
    quant_confidence_0_1 double precision,
    quant_confidence_effective_0_1 double precision,
    macro_action text,
    macro_news_shock boolean NOT NULL DEFAULT false,
    consensus_action text,
    consensus_status text,
    quant_weight_base double precision,
    quant_weight_effective double precision,
    shock_penalty_applied boolean NOT NULL DEFAULT false,
    anchor_price double precision,
    quant_foundation_path_ms double precision,
    war_room_eval_wall_ms double precision,
    outcome_return_pct double precision,
    outcome_eval_ts_ms bigint,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learn_tsfm_war_room_audit_symbol_created
    ON learn.tsfm_war_room_audit (symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_learn_tsfm_war_room_audit_pending_outcome
    ON learn.tsfm_war_room_audit (symbol, recorded_ts_ms DESC)
    WHERE outcome_return_pct IS NULL;
