CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS tsdb;

CREATE TABLE IF NOT EXISTS app.schema_migrations (
    filename text PRIMARY KEY,
    applied_ts timestamptz NOT NULL DEFAULT now()
);
