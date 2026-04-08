-- Prompt 26: Online-Drift-Zustand fuer Live-Gating (Signal-/Live-Broker lesen materialisierten State)

CREATE TABLE IF NOT EXISTS learn.online_drift_state (
    scope text PRIMARY KEY,
    effective_action text NOT NULL CHECK (
        effective_action IN ('ok', 'warn', 'shadow_only', 'hard_block')
    ),
    computed_at timestamptz NOT NULL DEFAULT now(),
    lookback_minutes integer NOT NULL DEFAULT 60,
    breakdown_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    drift_event_ids uuid[] NOT NULL DEFAULT '{}'::uuid[]
);

INSERT INTO learn.online_drift_state (scope, effective_action, lookback_minutes)
VALUES ('global', 'ok', 60)
ON CONFLICT (scope) DO NOTHING;

COMMENT ON TABLE learn.online_drift_state IS
    'Materialisierter Online-Drift fuer Gates; wird von learning-engine Evaluator aktualisiert.';

CREATE INDEX IF NOT EXISTS idx_learn_drift_events_online_detected
    ON learn.drift_events (detected_ts DESC)
    WHERE (details_json ->> 'drift_class') = 'online';
