-- Prompt 39: Apex Core Latency Telemetry (Signal-Engine -> Gateway -> Live-Broker -> Bitget)
CREATE TABLE IF NOT EXISTS app.apex_latency_audit (
    id bigserial PRIMARY KEY,
    signal_id text NOT NULL,
    execution_id uuid,
    trace_id text,
    apex_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_apex_latency_audit_signal
    ON app.apex_latency_audit (signal_id);

CREATE INDEX IF NOT EXISTS idx_apex_latency_audit_trace
    ON app.apex_latency_audit (trace_id);

CREATE INDEX IF NOT EXISTS idx_apex_latency_audit_exec
    ON app.apex_latency_audit (execution_id);

COMMENT ON TABLE app.apex_latency_audit IS
    'Apex-Trace: Service-Hops (t_enter/t_exit ns) + deltas_ms; Upsert pro signal_id.';
