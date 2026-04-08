-- Prompt 20: Strategy Execution Layer (State + Audit)

CREATE TABLE IF NOT EXISTS paper.strategy_state (
    key text PRIMARY KEY,
    paused boolean NOT NULL DEFAULT false,
    risk_off_until_ts_ms bigint NOT NULL DEFAULT 0,
    last_signal_id uuid,
    updated_ts_ms bigint NOT NULL
);

CREATE TABLE IF NOT EXISTS paper.strategy_events (
    event_id uuid PRIMARY KEY,
    ts_ms bigint NOT NULL,
    type text NOT NULL CHECK (
        type IN (
            'AUTO_OPEN',
            'AUTO_CLOSE',
            'NEWS_SHOCK',
            'DRAWING_TP_UPDATE',
            'STRUCTURE_FLIP_EXIT'
        )
    ),
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_paper_strategy_events_ts
    ON paper.strategy_events (ts_ms DESC);
