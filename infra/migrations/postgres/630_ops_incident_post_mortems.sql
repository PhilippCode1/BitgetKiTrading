-- P79: Strukturierter Post-Mortem-Datensatz (Snapshot + KI-RCA) bei global_halt / P0
CREATE TABLE IF NOT EXISTS ops.incident_post_mortems (
    id uuid PRIMARY KEY,
    created_ts timestamptz NOT NULL DEFAULT now(),
    trigger text NOT NULL,
    correlation_id text,
    started_ts timestamptz NOT NULL,
    completed_ts timestamptz,
    duration_ms int,
    redis_event_samples jsonb NOT NULL,
    service_health jsonb NOT NULL,
    llm_status text,
    llm_result jsonb,
    telegram_enqueued boolean NOT NULL DEFAULT false,
    report_url text
);

CREATE INDEX IF NOT EXISTS idx_ops_incident_post_mortems_created
    ON ops.incident_post_mortems (created_ts DESC);

COMMENT ON TABLE ops.incident_post_mortems IS
    'P79: Rohdaten (Eventbus+Health) + safety_incident_diagnosis (llm-orchestrator).';
