-- Prompt 19: Stop/TP Plaene, Quality Score, Audit Events

ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS plan_version text;
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS stop_plan_json jsonb;
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS tp_plan_json jsonb;
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS stop_quality_score integer;
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS rr_estimate numeric;
ALTER TABLE paper.positions ADD COLUMN IF NOT EXISTS plan_updated_ts_ms bigint;

CREATE TABLE IF NOT EXISTS paper.position_events (
    event_id uuid PRIMARY KEY,
    position_id uuid NOT NULL REFERENCES paper.positions (position_id),
    ts_ms bigint NOT NULL,
    type text NOT NULL CHECK (
        type IN (
            'PLAN_CREATED',
            'PLAN_UPDATED',
            'TP_HIT',
            'SL_HIT',
            'TRAILING_UPDATE',
            'RUNNER_TRAIL_HIT'
        )
    ),
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_paper_position_events_position_ts
    ON paper.position_events (position_id, ts_ms DESC);
