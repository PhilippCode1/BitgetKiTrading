CREATE TABLE IF NOT EXISTS raw_events (
    id uuid PRIMARY KEY,
    source text NOT NULL,
    inst_type text,
    channel text,
    inst_id text,
    action text NOT NULL,
    exchange_ts_ms bigint NULL,
    ingest_ts_ms bigint NOT NULL,
    payload jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_events_ingest_ts_ms
    ON raw_events (ingest_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_raw_events_channel_inst_id
    ON raw_events (channel, inst_id);
