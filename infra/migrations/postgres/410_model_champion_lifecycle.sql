-- Prompt 29: Champion-Historie, stabiler Rollback-Punkt, Promotions-Audit

CREATE TABLE IF NOT EXISTS app.model_champion_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL,
    run_id uuid NOT NULL REFERENCES app.model_runs (run_id) ON DELETE RESTRICT,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    ended_reason text,
    changed_by text,
    promotion_gate_report jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_model_champion_history_model_started
    ON app.model_champion_history (model_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_model_champion_history_open
    ON app.model_champion_history (model_name)
    WHERE ended_at IS NULL;

COMMENT ON TABLE app.model_champion_history IS
    'Zeitliche Champion-Zuweisungen; offene Zeile (ended_at IS NULL) entspricht Registry-Champion.';

CREATE TABLE IF NOT EXISTS app.model_stable_champion_checkpoint (
    model_name text PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES app.model_runs (run_id) ON DELETE RESTRICT,
    marked_at timestamptz NOT NULL DEFAULT now(),
    marked_by text NOT NULL,
    notes text
);

COMMENT ON TABLE app.model_stable_champion_checkpoint IS
    'Explizit markierter Rollback-Punkt pro model_name (Ops/Release).';
