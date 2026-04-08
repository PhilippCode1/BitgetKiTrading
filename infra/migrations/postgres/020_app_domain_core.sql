CREATE TABLE IF NOT EXISTS app.news_items (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    title text NOT NULL,
    url text NOT NULL UNIQUE,
    published_ts timestamptz,
    relevance_score numeric,
    sentiment numeric,
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    llm_summary_json jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.drawings (
    drawing_id uuid NOT NULL,
    parent_id uuid,
    revision integer NOT NULL DEFAULT 1,
    type text NOT NULL,
    timeframe text NOT NULL,
    geometry_json jsonb NOT NULL,
    style_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'active',
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (drawing_id, revision)
);

CREATE TABLE IF NOT EXISTS app.signals (
    signal_id uuid PRIMARY KEY,
    timeframe text NOT NULL,
    direction text NOT NULL CHECK (direction IN ('long', 'short', 'flat')),
    strength_0_100 numeric NOT NULL CHECK (strength_0_100 >= 0 AND strength_0_100 <= 100),
    probability_0_1 numeric NOT NULL CHECK (probability_0_1 >= 0 AND probability_0_1 <= 1),
    reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    stop_json jsonb,
    targets_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    state text NOT NULL DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS app.demo_trades (
    paper_trade_id uuid PRIMARY KEY,
    signal_id uuid REFERENCES app.signals (signal_id),
    opened_ts timestamptz NOT NULL,
    closed_ts timestamptz,
    fills_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    fees_total numeric NOT NULL DEFAULT 0,
    funding_total numeric NOT NULL DEFAULT 0,
    pnl_realized numeric NOT NULL DEFAULT 0,
    pnl_unrealized numeric NOT NULL DEFAULT 0,
    state text NOT NULL DEFAULT 'open',
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.strategy_versions (
    strategy_id text NOT NULL,
    version text NOT NULL,
    status text NOT NULL,
    definition_json jsonb NOT NULL,
    created_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (strategy_id, version)
);

CREATE TABLE IF NOT EXISTS app.model_runs (
    run_id uuid PRIMARY KEY,
    model_name text NOT NULL,
    version text NOT NULL,
    dataset_hash text NOT NULL,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    promoted_bool boolean NOT NULL DEFAULT false,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.audit_log (
    audit_id bigserial PRIMARY KEY,
    entity_schema text NOT NULL,
    entity_table text NOT NULL,
    entity_id text NOT NULL,
    action text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);
