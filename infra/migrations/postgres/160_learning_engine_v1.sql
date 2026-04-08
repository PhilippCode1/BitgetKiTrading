-- Prompt 23: Learning Engine V1 (Metriken, Patterns, Empfehlungen, Drift)

CREATE TABLE IF NOT EXISTS learn.strategy_metrics (
    strategy_id uuid NOT NULL REFERENCES learn.strategies (strategy_id) ON DELETE CASCADE,
    time_window text NOT NULL,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (strategy_id, time_window)
);

CREATE INDEX IF NOT EXISTS idx_learn_strategy_metrics_updated
    ON learn.strategy_metrics (updated_ts DESC);

CREATE TABLE IF NOT EXISTS learn.error_patterns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    time_window text NOT NULL,
    pattern_key text NOT NULL,
    count bigint NOT NULL,
    examples_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    UNIQUE (time_window, pattern_key)
);

CREATE INDEX IF NOT EXISTS idx_learn_error_patterns_time_window_count
    ON learn.error_patterns (time_window, count DESC);

CREATE TABLE IF NOT EXISTS learn.recommendations (
    rec_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type text NOT NULL CHECK (type IN ('signal_weights', 'risk_rules', 'promotion', 'retire')),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'approved', 'rejected', 'applied')),
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learn_recommendations_created
    ON learn.recommendations (created_ts DESC);

CREATE TABLE IF NOT EXISTS learn.drift_events (
    drift_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name text NOT NULL,
    detected_ts timestamptz NOT NULL DEFAULT now(),
    severity text NOT NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_learn_drift_detected
    ON learn.drift_events (detected_ts DESC);
