-- Prompt 24: Backtest / Replay / Purged CV

CREATE TABLE IF NOT EXISTS learn.backtest_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol text NOT NULL,
    timeframes_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    mode text NOT NULL CHECK (mode IN ('replay_to_bus', 'offline')),
    from_ts_ms bigint NOT NULL,
    to_ts_ms bigint NOT NULL,
    cv_method text NOT NULL CHECK (cv_method IN ('walk_forward', 'purged_kfold_embargo')),
    params_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learn_backtest_runs_created
    ON learn.backtest_runs (created_ts DESC);

CREATE TABLE IF NOT EXISTS learn.backtest_folds (
    fold_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES learn.backtest_runs (run_id) ON DELETE CASCADE,
    fold_index integer NOT NULL,
    train_range_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    test_range_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, fold_index)
);

CREATE INDEX IF NOT EXISTS idx_learn_backtest_folds_run
    ON learn.backtest_folds (run_id, fold_index);

CREATE TABLE IF NOT EXISTS learn.replay_sessions (
    session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_ts_ms bigint NOT NULL,
    to_ts_ms bigint NOT NULL,
    speed_factor numeric NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_ts timestamptz NOT NULL DEFAULT now()
);
