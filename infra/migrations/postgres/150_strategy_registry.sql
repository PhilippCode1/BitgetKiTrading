-- Prompt 22: Strategy Registry (Lifecycle + Versionen)

CREATE TABLE IF NOT EXISTS learn.strategies (
    strategy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    scope_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learn.strategy_versions (
    strategy_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id uuid NOT NULL REFERENCES learn.strategies (strategy_id) ON DELETE CASCADE,
    version text NOT NULL,
    definition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    parameters_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    risk_profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    UNIQUE (strategy_id, version)
);

CREATE INDEX IF NOT EXISTS idx_learn_strategy_versions_strategy
    ON learn.strategy_versions (strategy_id, created_ts DESC);

CREATE TABLE IF NOT EXISTS learn.strategy_status (
    strategy_id uuid PRIMARY KEY REFERENCES learn.strategies (strategy_id) ON DELETE CASCADE,
    current_status text NOT NULL CHECK (
        current_status IN ('promoted', 'candidate', 'shadow', 'retired')
    ),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learn.strategy_status_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id uuid NOT NULL REFERENCES learn.strategies (strategy_id) ON DELETE CASCADE,
    old_status text,
    new_status text NOT NULL,
    reason text,
    changed_by text NOT NULL DEFAULT 'system',
    ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learn_strategy_status_hist_strategy_ts
    ON learn.strategy_status_history (strategy_id, ts DESC);

CREATE TABLE IF NOT EXISTS learn.strategy_scores_rolling (
    strategy_id uuid NOT NULL REFERENCES learn.strategies (strategy_id) ON DELETE CASCADE,
    time_window text NOT NULL,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (strategy_id, time_window)
);
