-- Prompt 28: Ops / Monitoring (Checks, Stream Health, Alerts)

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.service_checks (
    check_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name text NOT NULL,
    check_type text NOT NULL CHECK (check_type IN ('health', 'ready', 'metrics', 'latency')),
    status text NOT NULL CHECK (status IN ('ok', 'degraded', 'fail')),
    latency_ms int NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_service_checks_name_ts
    ON ops.service_checks (service_name, ts DESC);

CREATE TABLE IF NOT EXISTS ops.stream_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stream text NOT NULL,
    group_name text NOT NULL,
    pending_count bigint NOT NULL DEFAULT 0,
    lag bigint NULL,
    last_generated_id text NULL,
    last_delivered_id text NULL,
    status text NOT NULL CHECK (status IN ('ok', 'degraded', 'fail')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_stream_checks_ts ON ops.stream_checks (ts DESC);

CREATE TABLE IF NOT EXISTS ops.data_freshness (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    datapoint text NOT NULL,
    last_ts_ms bigint NULL,
    age_ms bigint NULL,
    status text NOT NULL CHECK (status IN ('ok', 'warn', 'critical')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_data_freshness_ts ON ops.data_freshness (ts DESC);

CREATE TABLE IF NOT EXISTS ops.alerts (
    alert_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_key text NOT NULL UNIQUE,
    severity text NOT NULL CHECK (severity IN ('info', 'warn', 'critical')),
    title text NOT NULL,
    message text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'acked', 'resolved')),
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_alerts_state_created ON ops.alerts (state, created_ts DESC);

CREATE TABLE IF NOT EXISTS ops.incidents (
    incident_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_ts timestamptz NOT NULL DEFAULT now(),
    resolved_ts timestamptz NULL,
    summary text NOT NULL,
    related_alert_keys jsonb NOT NULL DEFAULT '[]'::jsonb
);
