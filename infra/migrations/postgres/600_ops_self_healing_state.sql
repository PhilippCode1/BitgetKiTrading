-- Prompt 74: Self-Healing Hub — Recovery State + Timeline

CREATE TABLE IF NOT EXISTS ops.self_healing_state (
    service_name text PRIMARY KEY,
    health_phase text NOT NULL CHECK (
        health_phase IN ('healthy', 'degraded', 'recovering')
    ),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    last_restart_ts timestamptz NULL,
    restart_events_ts jsonb NOT NULL DEFAULT '[]'::jsonb,
    timeline jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_event_detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ops_self_healing_state_phase
    ON ops.self_healing_state (health_phase, updated_ts DESC);

COMMENT ON TABLE ops.self_healing_state IS
  'Kernstatus fuer automatische/operator-gestuetzte Worker-Restarts; restart_events_ts = letzte Stunde (Sek. seit epoch im JSON-Array, max 3 relevant).';
